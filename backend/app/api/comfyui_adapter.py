"""ComfyUI adapter — submit workflow, poll for result, download image."""

from __future__ import annotations

import json
import random
import time
import uuid
from pathlib import Path

import certifi
import httpx

STATIC_IMAGES_DIR = Path(__file__).parent.parent / "static" / "images"
_POLL_INTERVAL = 1.0  # seconds between /history polls
_MAX_WAIT = 120.0  # seconds total timeout


def _inject_prompt(workflow: dict, prompt: str) -> dict:
    """Replace all string values equal to '{prompt}' with the actual prompt."""
    for _node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for key, val in inputs.items():
            if isinstance(val, str) and val.strip() == "{prompt}":
                inputs[key] = prompt
    return workflow


def _randomize_seed(workflow: dict) -> dict:
    """Randomize all seed values in the workflow."""
    for _node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        if "seed" in inputs and isinstance(inputs["seed"], int | float):
            inputs["seed"] = random.randint(0, 2**63 - 1)
    return workflow


def _call_comfyui_api(
    api_base: str,
    workflow_template: str,
    prompt: str,
    ssl_verify: bool = True,
) -> str:
    """
    Submit a workflow to ComfyUI, poll until done, download the result image.
    Returns the local URL path (e.g. /api/images/chat_1_abc123.png).
    """
    base = api_base.rstrip("/")

    workflow = json.loads(workflow_template)
    workflow = _inject_prompt(workflow, prompt)
    workflow = _randomize_seed(workflow)

    verify = certifi.where() if ssl_verify else False
    client_id = f"whainoel-{uuid.uuid4().hex[:8]}"

    with httpx.Client(timeout=120.0, verify=verify) as client:
        # 1) Submit workflow
        submit_resp = client.post(
            f"{base}/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        if submit_resp.status_code >= 400:
            raise RuntimeError(
                f"ComfyUI /prompt HTTP {submit_resp.status_code}: {submit_resp.text[:300]}"
            )
        prompt_id = submit_resp.json().get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI /prompt returned no prompt_id: {submit_resp.text[:300]}")

        # 2) Poll /history/{prompt_id} until outputs appear
        elapsed = 0.0
        while elapsed < _MAX_WAIT:
            time.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
            hist_resp = client.get(f"{base}/history/{prompt_id}")
            if hist_resp.status_code >= 400:
                continue
            hist_data = hist_resp.json()
            entry = hist_data.get(prompt_id)
            if not entry:
                continue
            outputs = entry.get("outputs", {})
            if not outputs:
                continue
            # Find the first image output across all nodes
            for _node_id, node_output in outputs.items():
                images = node_output.get("images", [])
                if images:
                    img = images[0]
                    filename = img["filename"]
                    subfolder = img.get("subfolder", "")
                    img_type = img.get("type", "output")

                    # 3) Download image
                    params = {"filename": filename, "subfolder": subfolder, "type": img_type}
                    download_resp = client.get(f"{base}/view", params=params)
                    if download_resp.status_code >= 400:
                        raise RuntimeError(
                            f"ComfyUI /view HTTP {download_resp.status_code}: {download_resp.text[:300]}"
                        )

                    STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                    ext = filename.rsplit(".", 1)[-1] if "." in filename else "png"
                    local_name = f"chat_comfyui_{uuid.uuid4().hex}.{ext}"
                    save_path = STATIC_IMAGES_DIR / local_name
                    save_path.write_bytes(download_resp.content)
                    return f"/api/images/{local_name}"

        raise RuntimeError(
            f"ComfyUI generation timed out after {_MAX_WAIT}s for prompt_id={prompt_id}"
        )

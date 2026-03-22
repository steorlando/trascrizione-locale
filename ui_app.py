#!/usr/bin/env python3
from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from app_runtime import configure_runtime_environment, get_env_file_path, get_resource_dir, get_runtime_dir

configure_runtime_environment()

from transcribe_local import (
    DEFAULT_AI_REVIEW_MODEL,
    PipelineError,
    SUPPORTED_AI_REVIEW_MODELS,
    SUPPORTED_EXTENSIONS,
    load_env_file,
    run_pipeline,
)

RESOURCE_DIR = get_resource_dir()
RUNTIME_DIR = get_runtime_dir()
UPLOADS_DIR = RUNTIME_DIR / "web_uploads"
RUNS_DIR = RUNTIME_DIR / "web_runs"
ALLOWED_EXTENSIONS = sorted(SUPPORTED_EXTENSIONS)
MODEL_PROFILES = {
    "quality": {
        "model": "large-v3",
        "label": "Massima accuratezza",
        "description": "large-v3: piu lento, ma migliore per qualita generale e italiano.",
    },
    "speed": {
        "model": "large-v3-turbo",
        "label": "Piu veloce",
        "description": "large-v3-turbo: molto rapido, con lieve calo di qualita.",
    },
}

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
load_env_file(get_env_file_path())

app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / "templates"),
    static_folder=str(RESOURCE_DIR / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB
JOB_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def build_job_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{uuid4().hex[:8]}"


def parse_optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def resolve_model(form) -> tuple[str, str]:
    profile = (form.get("quality_profile") or "quality").strip()
    manual_model = (form.get("model") or "large-v3").strip()

    if profile == "custom":
        return manual_model, profile

    if profile in MODEL_PROFILES:
        return MODEL_PROFILES[profile]["model"], profile

    return "large-v3", "quality"


def update_job(job_id: str, **updates) -> None:
    with JOB_LOCK:
        if job_id not in JOBS:
            JOBS[job_id] = {"job_id": job_id}
        JOBS[job_id].update(updates)


def get_job(job_id: str) -> dict | None:
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return None
        return dict(job)


def build_rendered_result(
    job_id: str,
    input_name: str,
    result: dict,
    selected_model: str,
    selected_profile: str,
) -> dict:
    txt_path = Path(result["txt_path"])
    srt_path = Path(result["srt_path"])
    json_path = Path(result["json_path"])

    return {
        "job_id": job_id,
        "input_name": input_name,
        "transcript": result["clean_text"],
        "txt_name": txt_path.name,
        "srt_name": srt_path.name,
        "json_name": json_path.name,
        "raw_txt_name": Path(result["raw_txt_path"]).name if result.get("raw_txt_path") else None,
        "model": selected_model,
        "quality_profile": selected_profile,
        "quality_profile_label": MODEL_PROFILES.get(selected_profile, {}).get("label", "Scelta manuale"),
        "device": result["device"],
        "diarization_enabled": result["diarization_enabled"],
        "ai_review_enabled": result["ai_review_enabled"],
        "ai_review_model": result["ai_review_model"],
    }


def run_job(
    *,
    job_id: str,
    input_path: Path,
    input_name: str,
    output_dir: Path,
    selected_model: str,
    selected_profile: str,
    form_data: dict,
) -> None:
    def progress_callback(stage: str, percent: int, message: str) -> None:
        update_job(
            job_id,
            status="running",
            stage=stage,
            percent=percent,
            message=message,
        )

    try:
        update_job(
            job_id,
            status="running",
            stage="starting",
            percent=1,
            message="Upload ricevuto. Avvio della trascrizione...",
        )

        result = run_pipeline(
            input_path=input_path,
            output_dir=output_dir,
            model=selected_model,
            language="it",
            device=form_data["device"],
            compute_type=form_data["compute_type"],
            beam_size=form_data["beam_size"],
            best_of=form_data["best_of"],
            temperature=form_data["temperature"],
            domain_prompt=form_data["domain_prompt"],
            hf_token=form_data["hf_token"],
            num_speakers=form_data["num_speakers"],
            min_speakers=form_data["min_speakers"],
            max_speakers=form_data["max_speakers"],
            no_diarization=form_data["no_diarization"],
            no_preprocess=form_data["no_preprocess"],
            no_noise_reduction=form_data["no_noise_reduction"],
            enable_ai_review=form_data["enable_ai_review"],
            ai_review_model=form_data["ai_review_model"],
            progress_callback=progress_callback,
        )

        rendered_result = build_rendered_result(
            job_id=job_id,
            input_name=input_name,
            result=result,
            selected_model=selected_model,
            selected_profile=selected_profile,
        )
        update_job(
            job_id,
            status="completed",
            stage="completed",
            percent=100,
            message="Trascrizione completata.",
            result=rendered_result,
        )
    except PipelineError as exc:
        update_job(
            job_id,
            status="error",
            stage="error",
            percent=100,
            error=str(exc),
            message="La trascrizione si è fermata con un errore.",
        )
    except Exception as exc:
        update_job(
            job_id,
            status="error",
            stage="error",
            percent=100,
            error=f"Errore inatteso durante la trascrizione: {exc}",
            message="La trascrizione si è fermata con un errore inatteso.",
        )


@app.get("/")
def index():
    return render_template(
        "index.html",
        allowed_extensions=", ".join(ALLOWED_EXTENSIONS),
        model_profiles=MODEL_PROFILES,
        ai_review_models=sorted(SUPPORTED_AI_REVIEW_MODELS),
        default_ai_review_model=DEFAULT_AI_REVIEW_MODEL,
        current_job=None,
        result=None,
        error=None,
    )


@app.post("/transcribe")
def transcribe():
    upload = request.files.get("audio_file")
    if upload is None or upload.filename is None or not upload.filename.strip():
        return render_template(
            "index.html",
            allowed_extensions=", ".join(ALLOWED_EXTENSIONS),
            model_profiles=MODEL_PROFILES,
            ai_review_models=sorted(SUPPORTED_AI_REVIEW_MODELS),
            default_ai_review_model=DEFAULT_AI_REVIEW_MODEL,
            current_job=None,
            result=None,
            error="Seleziona un file audio o video prima di avviare la trascrizione.",
        ), 400

    if not allowed_file(upload.filename):
        return render_template(
            "index.html",
            allowed_extensions=", ".join(ALLOWED_EXTENSIONS),
            model_profiles=MODEL_PROFILES,
            ai_review_models=sorted(SUPPORTED_AI_REVIEW_MODELS),
            default_ai_review_model=DEFAULT_AI_REVIEW_MODEL,
            current_job=None,
            result=None,
            error=(
                "Formato non supportato. Carica uno di questi formati: "
                + ", ".join(ALLOWED_EXTENSIONS)
            ),
        ), 400

    job_id = build_job_id()
    safe_name = secure_filename(upload.filename) or f"upload{Path(upload.filename).suffix.lower()}"
    upload_dir = UPLOADS_DIR / job_id
    output_dir = RUNS_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_path = upload_dir / safe_name
    upload.save(input_path)

    enable_diarization = request.form.get("enable_diarization") == "on"
    disable_preprocess = request.form.get("disable_preprocess") == "on"
    disable_noise_reduction = request.form.get("disable_noise_reduction") == "on"
    selected_model, selected_profile = resolve_model(request.form)

    try:
        form_data = {
            "device": (request.form.get("device") or "auto").strip(),
            "compute_type": (request.form.get("compute_type") or "").strip() or None,
            "beam_size": parse_optional_int(request.form.get("beam_size")) or 5,
            "best_of": parse_optional_int(request.form.get("best_of")) or 5,
            "temperature": float((request.form.get("temperature") or "0.0").strip()),
            "domain_prompt": (request.form.get("domain_prompt") or "").strip() or None,
            "hf_token": (request.form.get("hf_token") or "").strip() or None,
            "num_speakers": parse_optional_int(request.form.get("num_speakers")),
            "min_speakers": parse_optional_int(request.form.get("min_speakers")),
            "max_speakers": parse_optional_int(request.form.get("max_speakers")),
            "no_diarization": not enable_diarization,
            "no_preprocess": disable_preprocess,
            "no_noise_reduction": disable_noise_reduction,
            "enable_ai_review": request.form.get("enable_ai_review") == "on",
            "ai_review_model": (request.form.get("ai_review_model") or DEFAULT_AI_REVIEW_MODEL).strip(),
        }
        update_job(
            job_id,
            status="queued",
            stage="queued",
            percent=0,
            message="Richiesta ricevuta. La trascrizione sta per iniziare...",
            error=None,
            input_name=upload.filename,
        )
        worker = threading.Thread(
            target=run_job,
            kwargs={
                "job_id": job_id,
                "input_path": input_path,
                "input_name": upload.filename,
                "output_dir": output_dir,
                "selected_model": selected_model,
                "selected_profile": selected_profile,
                "form_data": form_data,
            },
            daemon=True,
        )
        worker.start()
    except ValueError:
        return render_template(
            "index.html",
            allowed_extensions=", ".join(ALLOWED_EXTENSIONS),
            model_profiles=MODEL_PROFILES,
            ai_review_models=sorted(SUPPORTED_AI_REVIEW_MODELS),
            default_ai_review_model=DEFAULT_AI_REVIEW_MODEL,
            current_job=None,
            result=None,
            error="I campi numerici non sono validi. Controlla beam size, best of, temperatura e speaker.",
        ), 400
    except Exception as exc:
        return render_template(
            "index.html",
            allowed_extensions=", ".join(ALLOWED_EXTENSIONS),
            model_profiles=MODEL_PROFILES,
            ai_review_models=sorted(SUPPORTED_AI_REVIEW_MODELS),
            default_ai_review_model=DEFAULT_AI_REVIEW_MODEL,
            current_job=None,
            result=None,
            error=f"Errore inatteso durante la trascrizione: {exc}",
        ), 500

    return redirect(url_for("job_page", job_id=job_id))


@app.get("/jobs/<job_id>")
def job_page(job_id: str):
    job = get_job(job_id)
    if job is None:
        abort(404)

    return render_template(
        "index.html",
        allowed_extensions=", ".join(ALLOWED_EXTENSIONS),
        model_profiles=MODEL_PROFILES,
        ai_review_models=sorted(SUPPORTED_AI_REVIEW_MODELS),
        default_ai_review_model=DEFAULT_AI_REVIEW_MODEL,
        current_job=job,
        result=job.get("result"),
        error=job.get("error"),
    )


@app.get("/api/jobs/<job_id>")
def job_api(job_id: str):
    job = get_job(job_id)
    if job is None:
        abort(404)

    payload = {
        "job_id": job_id,
        "status": job.get("status"),
        "stage": job.get("stage"),
        "percent": job.get("percent", 0),
        "message": job.get("message"),
        "error": job.get("error"),
        "has_result": job.get("result") is not None,
    }
    return jsonify(payload)


@app.get("/download/<job_id>/<file_kind>")
def download_file(job_id: str, file_kind: str):
    allowed_kinds = {"txt", "srt", "json", "raw_txt"}
    if file_kind not in allowed_kinds:
        abort(404)

    job_dir = RUNS_DIR / job_id
    if not job_dir.exists():
        abort(404)

    pattern = "*.raw.txt" if file_kind == "raw_txt" else f"*.{file_kind}"
    matches = list(job_dir.glob(pattern))
    if not matches:
        abort(404)

    return send_file(matches[0], as_attachment=True, download_name=matches[0].name)


if __name__ == "__main__":
    host = os.environ.get("TRANSCRIBE_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("TRANSCRIBE_UI_PORT", "8000"))
    app.run(host=host, port=port, debug=False)

#!/usr/bin/env python3
"""
Local transcription pipeline for Italian audio/video files.

Features:
- audio/video ingestion via ffmpeg
- optional preprocessing (mono, resample, high-pass, denoise, loudness normalization)
- transcription with faster-whisper
- optional speaker diarization with pyannote.audio
- domain prompt support through Whisper initial_prompt
- output generation in TXT, SRT and JSON

Notes:
- diarization is fully local at inference time, but pyannote models are usually
  downloaded once from Hugging Face. A Hugging Face access token is often needed
  to download the diarization checkpoint the first time.
- on macOS, CPU execution is the most realistic default unless the user has a
  CUDA-capable external environment.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from app_runtime import configure_runtime_environment, get_env_file_path, get_resource_dir


configure_runtime_environment()


SUPPORTED_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".wav",
    ".mp4",
    ".mkv",
    ".mov",
    ".aac",
    ".flac",
    ".ogg",
}


@dataclass
class SegmentRecord:
    id: int
    start: float
    end: float
    text: str
    speaker: Optional[str]
    words: List[Dict[str, Any]]


class PipelineError(RuntimeError):
    """Raised for user-facing pipeline failures."""


ProgressCallback = Optional[Callable[[str, int, str], None]]
DEFAULT_AI_REVIEW_MODEL = "gpt-4.1-mini"
SUPPORTED_AI_REVIEW_MODELS = {
    "gpt-4.1-mini",
    "gpt-4.1-nano",
}
SUPPORTED_UI_LANGUAGES = {
    "it": "Italiano",
    "en": "English",
}


def notify_progress(
    progress_callback: ProgressCallback,
    stage: str,
    percent: int,
    message: str,
) -> None:
    if progress_callback is None:
        return
    bounded_percent = max(0, min(100, int(percent)))
    progress_callback(stage, bounded_percent, message)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def ensure_command(command: str) -> None:
    if shutil.which(command) is None:
        raise PipelineError(
            f"Comando mancante: '{command}'. Installalo e riprova. "
            f"Su macOS: brew install {command}"
        )


def check_input_file(path: Path) -> None:
    if not path.exists():
        raise PipelineError(f"File input non trovato: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise PipelineError(
            "Formato non supportato. Estensioni consentite: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS))
        )


def run_command(command: Sequence[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise PipelineError(f"Comando non trovato: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise PipelineError(
            f"Comando fallito con codice {exc.returncode}: {' '.join(command)}"
        ) from exc


def resolve_ffmpeg_command() -> str:
    try:
        import imageio_ffmpeg  # type: ignore

        ffmpeg_exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if ffmpeg_exe.exists():
            return str(ffmpeg_exe)
    except Exception:
        pass

    bundled_ffmpeg = get_resource_dir() / "imageio_ffmpeg" / "binaries"
    for candidate in bundled_ffmpeg.glob("ffmpeg-*"):
        if candidate.is_file():
            return str(candidate)

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    raise PipelineError(
        "ffmpeg non trovato. Installa imageio-ffmpeg o ffmpeg di sistema e riprova."
    )


def ffmpeg_preprocess(
    input_path: Path,
    output_path: Path,
    ffmpeg_command: str,
    enable_noise_reduction: bool = True,
) -> None:
    """
    Create a transcription-friendly WAV:
    - mono
    - 16 kHz
    - high-pass to remove low-frequency rumble
    - optional spectral denoise
    - loudness normalization
    """
    filters = ["highpass=f=80"]
    if enable_noise_reduction:
        filters.append("afftdn=nf=-25")
    filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    audio_filter = ",".join(filters)

    command = [
        ffmpeg_command,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        audio_filter,
        str(output_path),
    ]
    run_command(command)


def ffmpeg_convert_to_wav(input_path: Path, output_path: Path, ffmpeg_command: str) -> None:
    command = [
        ffmpeg_command,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]
    run_command(command)


def import_faster_whisper() -> Any:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise PipelineError(
            "Dipendenza mancante: faster-whisper. "
            "Installa i pacchetti del requirements prima di eseguire lo script."
        ) from exc
    return WhisperModel


def import_torch() -> Any:
    try:
        import torch  # type: ignore
    except ImportError as exc:
        raise PipelineError(
            "Dipendenza mancante: torch. "
            "Installa i pacchetti del requirements prima di eseguire lo script."
        ) from exc
    return torch


def import_openai() -> Any:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise PipelineError(
            "Dipendenza mancante: openai. "
            "Installa i pacchetti del requirements prima di usare la revisione AI."
        ) from exc
    return OpenAI


def detect_device(explicit_device: str) -> str:
    if explicit_device == "cuda":
        torch = import_torch()
        if torch.cuda.is_available():
            return "cuda"
        raise PipelineError(
            "Hai selezionato CUDA, ma in questo ambiente non è disponibile. "
            "Su questo Mac usa `auto` o `cpu`."
        )

    if explicit_device != "auto":
        return explicit_device

    torch = import_torch()
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def default_compute_type(device: str) -> str:
    if device == "cuda":
        return "float16"
    return "int8"


def load_whisper_model(model_name: str, device: str, compute_type: str) -> Any:
    WhisperModel = import_faster_whisper()
    try:
        return WhisperModel(model_name, device=device, compute_type=compute_type)
    except Exception as exc:  # pragma: no cover - model loading is env-specific
        raise PipelineError(
            "Impossibile caricare il modello Whisper richiesto. "
            "Controlla nome modello, memoria disponibile e installazione di faster-whisper."
        ) from exc


def transcribe_audio(
    audio_path: Path,
    model_name: str,
    device: str,
    compute_type: str,
    language: str,
    beam_size: int,
    best_of: int,
    temperature: float,
    domain_prompt: Optional[str],
    progress_callback: ProgressCallback = None,
) -> Tuple[List[SegmentRecord], Dict[str, Any]]:
    notify_progress(progress_callback, "transcription", 24, "Caricamento del modello Whisper...")
    model = load_whisper_model(model_name=model_name, device=device, compute_type=compute_type)

    transcribe_kwargs: Dict[str, Any] = {
        "language": language,
        "beam_size": beam_size,
        "best_of": best_of,
        "temperature": temperature,
        "word_timestamps": True,
        "condition_on_previous_text": True,
        "vad_filter": False,
    }
    if domain_prompt:
        transcribe_kwargs["initial_prompt"] = domain_prompt

    try:
        segments, info = model.transcribe(str(audio_path), **transcribe_kwargs)
    except Exception as exc:  # pragma: no cover - runtime depends on model/audio
        raise PipelineError(
            "Errore durante la trascrizione. "
            "Prova un modello più piccolo o disabilita il preprocessing se il file è problematico."
        ) from exc

    results: List[SegmentRecord] = []
    total_duration = getattr(info, "duration", None) or 0
    notify_progress(progress_callback, "transcription", 28, "Trascrizione in corso...")
    for idx, segment in enumerate(segments):
        words: List[Dict[str, Any]] = []
        for word in segment.words or []:
            words.append(
                {
                    "start": getattr(word, "start", None),
                    "end": getattr(word, "end", None),
                    "word": getattr(word, "word", "").strip(),
                    "probability": getattr(word, "probability", None),
                }
            )
        results.append(
            SegmentRecord(
                id=idx,
                start=float(segment.start),
                end=float(segment.end),
                text=segment.text.strip(),
                speaker=None,
                words=words,
            )
        )
        if total_duration:
            fraction = min(max(float(segment.end) / float(total_duration), 0.0), 1.0)
            percent = 28 + int(fraction * 52)
            notify_progress(
                progress_callback,
                "transcription",
                percent,
                (
                    "Trascrizione in corso... "
                    f"{format_timestamp(min(float(segment.end), float(total_duration)))} / "
                    f"{format_timestamp(float(total_duration))}"
                ),
            )

    notify_progress(progress_callback, "transcription", 82, "Trascrizione completata.")

    info_dict = {
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "duration_after_vad": getattr(info, "duration_after_vad", None),
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
    }
    return results, info_dict


def import_pyannote() -> Any:
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except ImportError as exc:
        raise PipelineError(
            "Dipendenza mancante: pyannote.audio. "
            "Installa i pacchetti del requirements o usa --no_diarization."
        ) from exc
    return Pipeline


def diarize_audio(
    audio_path: Path,
    hf_token: Optional[str],
    device: str,
    num_speakers: Optional[int],
    min_speakers: Optional[int],
    max_speakers: Optional[int],
) -> List[Tuple[float, float, str]]:
    Pipeline = import_pyannote()
    token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        raise PipelineError(
            "La diarizzazione richiede un token Hugging Face per scaricare il modello "
            "la prima volta. Imposta HF_TOKEN oppure usa --hf_token."
        )

    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=token,
        )
    except Exception as exc:  # pragma: no cover - network/model gating specific
        raise PipelineError(
            "Impossibile caricare il modello di diarizzazione pyannote. "
            "Verifica il token Hugging Face e di aver accettato i termini del modello."
        ) from exc

    torch = import_torch()
    target_device = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
    try:
        pipeline.to(torch.device(target_device))
    except Exception:
        pass

    diarization_kwargs: Dict[str, Any] = {}
    if num_speakers is not None:
        diarization_kwargs["num_speakers"] = num_speakers
    if min_speakers is not None:
        diarization_kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        diarization_kwargs["max_speakers"] = max_speakers

    try:
        diarization = pipeline(str(audio_path), **diarization_kwargs)
    except Exception as exc:  # pragma: no cover
        raise PipelineError(
            "Errore durante la diarizzazione. "
            "Prova ad aggiungere --num_speakers o a disabilitare la diarizzazione."
        ) from exc

    speaker_turns: List[Tuple[float, float, str]] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_turns.append((float(turn.start), float(turn.end), str(speaker)))
    return speaker_turns


def overlap_duration(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def attach_speakers(
    segments: List[SegmentRecord],
    speaker_turns: List[Tuple[float, float, str]],
) -> None:
    if not speaker_turns:
        return

    for segment in segments:
        best_speaker = None
        best_overlap = 0.0
        for turn_start, turn_end, speaker in speaker_turns:
            overlap = overlap_duration(segment.start, segment.end, turn_start, turn_end)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        segment.speaker = best_speaker or "SPEAKER_UNK"


def format_timestamp(seconds: float, srt: bool = False) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    millis = total_ms % 1000
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def build_clean_text(segments: Iterable[SegmentRecord], include_speakers: bool) -> str:
    lines: List[str] = []
    current_speaker: Optional[str] = None
    current_text: List[str] = []

    for segment in segments:
        speaker = segment.speaker if include_speakers else None
        if speaker != current_speaker and current_text:
            if include_speakers and current_speaker:
                lines.append(f"{current_speaker}: {' '.join(current_text).strip()}")
            else:
                lines.append(" ".join(current_text).strip())
            current_text = []
        current_speaker = speaker
        current_text.append(segment.text)

    if current_text:
        if include_speakers and current_speaker:
            lines.append(f"{current_speaker}: {' '.join(current_text).strip()}")
        else:
            lines.append(" ".join(current_text).strip())

    return "\n\n".join(line for line in lines if line)


def review_transcript_with_openai(
    text: str,
    model: str,
    language: str,
    domain_prompt: Optional[str],
    progress_callback: ProgressCallback = None,
) -> Tuple[str, Dict[str, Any]]:
    if model not in SUPPORTED_AI_REVIEW_MODELS:
        raise PipelineError(
            "Modello OpenAI non supportato per la revisione AI. "
            f"Scegli uno tra: {', '.join(sorted(SUPPORTED_AI_REVIEW_MODELS))}"
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise PipelineError(
            "La revisione AI richiede OPENAI_API_KEY. "
            f"Scrivila nel file {get_env_file_path()}."
        )

    notify_progress(progress_callback, "ai_review", 97, "Revisione AI del testo in corso...")
    OpenAI = import_openai()
    client = OpenAI(api_key=api_key)

    language_name = SUPPORTED_UI_LANGUAGES.get(language, language)
    domain_note = (
        "Terms or names to treat with extra care: "
        f"{domain_prompt.strip()}"
        if domain_prompt
        else "No extra domain terms were provided."
    )

    instructions = (
        f"You are a conservative transcript editor for {language_name}. "
        "Improve the text without rewriting it. "
        "Add punctuation, capitalization, and paragraph breaks where needed. "
        "Correct only very obvious spelling or lexical errors. "
        "Do not summarize. Do not paraphrase. Do not make the text more elegant. "
        "Do not change meaning. Do not invent missing content. "
        "Preserve speaker labels exactly as written, including SPEAKER_00, SPEAKER_01, and similar tags. "
        "Keep technical terminology, acronyms, and plausible proper nouns intact. "
        "Return only the final corrected text, with no notes or commentary."
    )

    user_input = (
        f"Target language: {language_name}\n"
        f"{domain_note}\n\n"
        "Transcript to correct minimally:\n\n"
        f"{text}"
    )

    try:
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=user_input,
            max_output_tokens=12000,
        )
    except Exception as exc:  # pragma: no cover - external API dependent
        raise PipelineError(
            "Errore durante la revisione AI OpenAI. "
            "Controlla OPENAI_API_KEY, credito disponibile e connettivita di rete."
        ) from exc

    reviewed_text = (response.output_text or "").strip()
    if not reviewed_text:
        raise PipelineError("La revisione AI non ha restituito testo utilizzabile.")

    usage = getattr(response, "usage", None)
    review_metadata = {
        "enabled": True,
        "model": model,
        "response_id": getattr(response, "id", None),
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
            "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
        },
    }
    notify_progress(progress_callback, "ai_review", 99, "Revisione AI completata.")
    return reviewed_text, review_metadata


def write_txt(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def write_srt(path: Path, segments: Sequence[SegmentRecord]) -> None:
    chunks: List[str] = []
    for index, segment in enumerate(segments, start=1):
        text = segment.text
        if segment.speaker:
            text = f"{segment.speaker}: {text}"
        chunks.append(
            "\n".join(
                [
                    str(index),
                    f"{format_timestamp(segment.start, srt=True)} --> {format_timestamp(segment.end, srt=True)}",
                    text,
                ]
            )
        )
    path.write_text("\n\n".join(chunks).strip() + "\n", encoding="utf-8")


def write_json(
    path: Path,
    input_path: Path,
    processed_audio_path: Path,
    metadata: Dict[str, Any],
    diarization_enabled: bool,
    preprocessing_enabled: bool,
    domain_prompt: Optional[str],
    final_text: str,
    raw_text: str,
    ai_review: Dict[str, Any],
    segments: Sequence[SegmentRecord],
    speaker_turns: Sequence[Tuple[float, float, str]],
) -> None:
    payload = {
        "input_file": str(input_path),
        "processed_audio_file": str(processed_audio_path),
        "metadata": metadata,
        "config": {
            "diarization_enabled": diarization_enabled,
            "preprocessing_enabled": preprocessing_enabled,
            "domain_prompt": domain_prompt,
            "ai_review": ai_review,
        },
        "raw_text": raw_text,
        "final_text": final_text,
        "speaker_turns": [
            {"start": start, "end": end, "speaker": speaker}
            for start, end, speaker in speaker_turns
        ],
        "segments": [asdict(segment) for segment in segments],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline locale per trascrizione italiana con faster-whisper e diarizzazione opzionale."
    )
    parser.add_argument("input", type=Path, help="File audio/video di input.")
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("output_transcripts"),
        help="Cartella di output. Default: output_transcripts",
    )
    parser.add_argument(
        "--model",
        default="large-v3",
        help="Modello faster-whisper da usare. Default: large-v3",
    )
    parser.add_argument(
        "--language",
        default="it",
        help="Lingua forzata per la trascrizione. Default: it",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Device per inferenza. Default: auto",
    )
    parser.add_argument(
        "--compute_type",
        default=None,
        help="Compute type per faster-whisper. Default automatico: float16 su CUDA, int8 su CPU.",
    )
    parser.add_argument(
        "--beam_size",
        type=int,
        default=5,
        help="Beam size per la decodifica. Default: 5",
    )
    parser.add_argument(
        "--best_of",
        type=int,
        default=5,
        help="Numero di candidati in sampling. Default: 5",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Temperatura di decodifica. Default: 0.0",
    )
    parser.add_argument(
        "--domain_prompt",
        default=None,
        help=(
            "Prompt di dominio con parole chiave, sigle, nomi propri o lessico tecnico. "
            "Viene passato a Whisper come initial_prompt."
        ),
    )
    parser.add_argument(
        "--hf_token",
        default=None,
        help="Token Hugging Face per scaricare il modello di diarizzazione pyannote.",
    )
    parser.add_argument(
        "--num_speakers",
        type=int,
        default=None,
        help="Numero esatto di parlanti, se noto.",
    )
    parser.add_argument(
        "--min_speakers",
        type=int,
        default=None,
        help="Numero minimo di parlanti per la diarizzazione.",
    )
    parser.add_argument(
        "--max_speakers",
        type=int,
        default=None,
        help="Numero massimo di parlanti per la diarizzazione.",
    )
    parser.add_argument(
        "--no_diarization",
        action="store_true",
        help="Disattiva la diarizzazione speaker.",
    )
    parser.add_argument(
        "--no_preprocess",
        action="store_true",
        help="Disattiva il preprocessing audio.",
    )
    parser.add_argument(
        "--no_noise_reduction",
        action="store_true",
        help="Mantiene il preprocessing ma senza il filtro di noise reduction afftdn.",
    )
    parser.add_argument(
        "--enable_ai_review",
        action="store_true",
        help="Attiva una revisione finale del testo con OpenAI per punteggiatura e correzioni minime.",
    )
    parser.add_argument(
        "--ai_review_model",
        default=DEFAULT_AI_REVIEW_MODEL,
        help=f"Modello OpenAI per la revisione finale. Default: {DEFAULT_AI_REVIEW_MODEL}",
    )
    return parser.parse_args()


def run_pipeline(
    input_path: Path,
    output_dir: Path,
    model: str = "large-v3",
    language: str = "it",
    device: str = "auto",
    compute_type: Optional[str] = None,
    beam_size: int = 5,
    best_of: int = 5,
    temperature: float = 0.0,
    domain_prompt: Optional[str] = None,
    hf_token: Optional[str] = None,
    num_speakers: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    no_diarization: bool = False,
    no_preprocess: bool = False,
    no_noise_reduction: bool = False,
    enable_ai_review: bool = False,
    ai_review_model: str = DEFAULT_AI_REVIEW_MODEL,
    progress_callback: ProgressCallback = None,
) -> Dict[str, Any]:
    load_env_file(get_env_file_path())
    notify_progress(progress_callback, "starting", 2, "Preparazione della pipeline...")
    ffmpeg_command = resolve_ffmpeg_command()
    check_input_file(input_path)

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = input_path.stem
    processed_audio_path = output_dir / f"{base_name}.preprocessed.wav"

    preprocessing_enabled = not no_preprocess
    diarization_enabled = not no_diarization

    notify_progress(progress_callback, "preprocess", 8, "Preparazione audio in corso...")
    if preprocessing_enabled:
        ffmpeg_preprocess(
            input_path=input_path,
            output_path=processed_audio_path,
            ffmpeg_command=ffmpeg_command,
            enable_noise_reduction=not no_noise_reduction,
        )
    else:
        notify_progress(progress_callback, "preprocess", 8, "Conversione audio in WAV...")
        ffmpeg_convert_to_wav(
            input_path=input_path,
            output_path=processed_audio_path,
            ffmpeg_command=ffmpeg_command,
        )

    notify_progress(progress_callback, "preprocess", 18, "Audio pronto per la trascrizione.")

    resolved_device = detect_device(device)
    resolved_compute_type = compute_type or default_compute_type(resolved_device)

    segments, metadata = transcribe_audio(
        audio_path=processed_audio_path,
        model_name=model,
        device=resolved_device,
        compute_type=resolved_compute_type,
        language=language,
        beam_size=beam_size,
        best_of=best_of,
        temperature=temperature,
        domain_prompt=domain_prompt,
        progress_callback=progress_callback,
    )

    speaker_turns: List[Tuple[float, float, str]] = []
    if diarization_enabled:
        notify_progress(progress_callback, "diarization", 86, "Diarizzazione speaker in corso...")
        speaker_turns = diarize_audio(
            audio_path=processed_audio_path,
            hf_token=hf_token,
            device=resolved_device,
            num_speakers=num_speakers,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        attach_speakers(segments, speaker_turns)
        notify_progress(progress_callback, "diarization", 93, "Diarizzazione completata.")

    txt_path = output_dir / f"{base_name}.txt"
    raw_txt_path = output_dir / f"{base_name}.raw.txt"
    srt_path = output_dir / f"{base_name}.srt"
    json_path = output_dir / f"{base_name}.json"

    notify_progress(progress_callback, "writing", 96, "Salvataggio dei file di output...")
    raw_text = build_clean_text(segments, include_speakers=diarization_enabled)
    final_text = raw_text
    ai_review_metadata: Dict[str, Any] = {"enabled": False, "model": None}

    if enable_ai_review:
        write_txt(raw_txt_path, raw_text)
        final_text, ai_review_metadata = review_transcript_with_openai(
            text=raw_text,
            model=ai_review_model,
            language=language,
            domain_prompt=domain_prompt,
            progress_callback=progress_callback,
        )

    write_txt(txt_path, final_text)
    write_srt(srt_path, segments)
    write_json(
        path=json_path,
        input_path=input_path.resolve(),
        processed_audio_path=processed_audio_path.resolve(),
        metadata=metadata,
        diarization_enabled=diarization_enabled,
        preprocessing_enabled=preprocessing_enabled,
        domain_prompt=domain_prompt,
        final_text=final_text,
        raw_text=raw_text,
        ai_review=ai_review_metadata,
        segments=segments,
        speaker_turns=speaker_turns,
    )
    notify_progress(progress_callback, "completed", 100, "Trascrizione completata.")

    return {
        "txt_path": txt_path,
        "raw_txt_path": raw_txt_path if enable_ai_review else None,
        "srt_path": srt_path,
        "json_path": json_path,
        "processed_audio_path": processed_audio_path,
        "clean_text": final_text,
        "raw_text": raw_text,
        "segments": segments,
        "speaker_turns": speaker_turns,
        "metadata": metadata,
        "language": metadata.get("language", language),
        "device": resolved_device,
        "compute_type": resolved_compute_type,
        "diarization_enabled": diarization_enabled,
        "preprocessing_enabled": preprocessing_enabled,
        "ai_review_enabled": enable_ai_review,
        "ai_review_model": ai_review_model if enable_ai_review else None,
        "ai_review_metadata": ai_review_metadata,
    }


def main() -> int:
    args = parse_args()

    try:
        result = run_pipeline(
            input_path=args.input,
            output_dir=args.output_dir,
            model=args.model,
            language=args.language,
            device=args.device,
            compute_type=args.compute_type,
            beam_size=args.beam_size,
            best_of=args.best_of,
            temperature=args.temperature,
            domain_prompt=args.domain_prompt,
            hf_token=args.hf_token,
            num_speakers=args.num_speakers,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
            no_diarization=args.no_diarization,
            no_preprocess=args.no_preprocess,
            no_noise_reduction=args.no_noise_reduction,
            enable_ai_review=args.enable_ai_review,
            ai_review_model=args.ai_review_model,
        )

        print("Trascrizione completata con successo.")
        print(f"TXT : {result['txt_path']}")
        print(f"SRT : {result['srt_path']}")
        print(f"JSON: {result['json_path']}")
        return 0

    except PipelineError as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrotto dall'utente.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

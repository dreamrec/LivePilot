"""Benchmark music-audio embedding backends on LivePilot's real capture families.

THE QUESTION
------------
Can the embedding tell "a different render of the same idea" from "a genuinely
different version"? That is the only property the taste head needs: it trains on
listen_ab keep/undone pairs, so it must separate iterations of the same session.

THE METRIC (identical for every backend)
----------------------------------------
For each capture, cut N non-overlapping W-second windows and embed each one.

  within_spread  = mean pairwise cosine distance among windows of the SAME
                   capture. This is the measurement noise floor: how much the
                   embedding moves just from looking at a different part of one
                   take.
  between_dist   = mean cosine distance between windows of DIFFERENT captures
                   in the same family (= different iterations of one idea).
  SNR            = between_dist / within_spread

SNR > 1 means iterations are further apart than the model's own within-take
wobble — i.e. the signal survives the noise floor. Higher is better. SNR near
1 means the embedding cannot tell iterations apart at all.

Embeddings are L2-normalised before cosine, which is standard and makes the
scale comparable across models of different dimensionality.

Deterministic: fixed windows, no random crops, no sampling.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import time

import numpy as np
import soundfile as sf


AUDIO_EXTS = (".wav", ".aiff", ".aif")
# Hardware smoke tones (sine / noise / pulse), not musical iterations. Kept
# separate because their embeddings say nothing about kept-vs-superseded music.
SYNTHETIC_PREFIXES = ("manual_",)


def family_key(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    tokens = stem.split("_")
    return "_".join(tokens[:2]) if len(tokens) >= 2 else stem


def load_mono(path: str, target_sr: int) -> np.ndarray:
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if sr != target_sr:
        import scipy.signal as sps
        g = np.gcd(int(sr), int(target_sr))
        mono = sps.resample_poly(mono, target_sr // g, sr // g)
    return mono.astype(np.float32)


def windows(mono: np.ndarray, sr: int, win_s: float, max_n: int) -> list:
    n = int(win_s * sr)
    if len(mono) < n:
        return []
    out = []
    for i in range(max_n):
        a = i * n
        if a + n > len(mono):
            break
        out.append(mono[a:a + n])
    return out


# --- backends ---------------------------------------------------------------

class Backend:
    name = ""
    sr = 0

    def embed(self, chunks):  # -> (n, dim)
        raise NotImplementedError


class MertBackend(Backend):
    def __init__(self, model_id, device):
        import torch
        from transformers import AutoModel, Wav2Vec2FeatureExtractor
        self.name = model_id
        self.sr = 24000
        self.torch = torch
        self.device = device
        self.fe = Wav2Vec2FeatureExtractor.from_pretrained(model_id, trust_remote_code=True)
        m = AutoModel.from_pretrained(model_id, trust_remote_code=True).to(device)
        m.train(False)  # inference mode
        self.model = m

    def embed(self, chunks):
        out = []
        for c in chunks:
            inp = self.fe(c, sampling_rate=self.sr, return_tensors="pt")
            inp = {k: v.to(self.device) for k, v in inp.items()}
            with self.torch.no_grad():
                h = self.model(**inp).last_hidden_state  # (1, T, D) — last layer
            out.append(h.mean(dim=1).squeeze(0).float().cpu().numpy())
        return np.stack(out)


class ClapBackend(Backend):
    def __init__(self, model_id, device):
        import torch
        from transformers import ClapModel, ClapProcessor
        self.name = model_id
        self.sr = 48000
        self.torch = torch
        self.device = device
        self.proc = ClapProcessor.from_pretrained(model_id)
        m = ClapModel.from_pretrained(model_id).to(device)
        m.train(False)  # inference mode
        self.model = m

    def _process(self, c):
        # transformers >=5 renamed the kwarg audios -> audio.
        try:
            return self.proc(audio=c, sampling_rate=self.sr, return_tensors="pt")
        except (TypeError, ValueError):
            return self.proc(audios=c, sampling_rate=self.sr, return_tensors="pt")

    def embed(self, chunks):
        out = []
        for c in chunks:
            inp = self._process(c)
            inp = {k: v.to(self.device) for k, v in inp.items()}
            with self.torch.no_grad():
                e = self.model.get_audio_features(**inp)
            # transformers <5 returned a tensor; >=5 returns
            # BaseModelOutputWithPooling whose pooler_output is the projected
            # (512-d) joint-space audio embedding — the CLAP embedding proper.
            if not self.torch.is_tensor(e):
                e = getattr(e, "pooler_output", None)
                if e is None:
                    raise RuntimeError("CLAP returned no pooler_output")
            out.append(e.squeeze(0).float().cpu().numpy())
        return np.stack(out)


# --- metric -----------------------------------------------------------------

def l2(x):
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-12)


def cos_dist(a, b):
    return float(1.0 - np.dot(a, b))


def evaluate(backend, families, win_s, max_win):
    per_file = {}
    encode_ms = []

    for paths in families.values():
        for p in paths:
            if p in per_file:
                continue
            mono = load_mono(p, backend.sr)
            chunks = windows(mono, backend.sr, win_s, max_win)
            if len(chunks) < 2:
                continue
            t0 = time.perf_counter()
            emb = backend.embed(chunks)
            encode_ms.append((time.perf_counter() - t0) * 1000.0 / len(chunks))
            per_file[p] = l2(emb)

    fam_rows = []
    for key, paths in sorted(families.items()):
        usable = [p for p in paths if p in per_file]
        if len(usable) < 2:
            continue
        within = []
        for p in usable:
            e = per_file[p]
            for i in range(len(e)):
                for j in range(i + 1, len(e)):
                    within.append(cos_dist(e[i], e[j]))
        between = []
        for i in range(len(usable)):
            for j in range(i + 1, len(usable)):
                for a in per_file[usable[i]]:
                    for b in per_file[usable[j]]:
                        between.append(cos_dist(a, b))
        if not within or not between:
            continue
        w = float(np.mean(within))
        b = float(np.mean(between))
        fam_rows.append({
            "family": key, "n_files": len(usable),
            "within_spread": w, "between_dist": b,
            "snr": (b / w) if w > 0 else float("inf"),
            "synthetic": key.startswith(SYNTHETIC_PREFIXES),
        })

    return {
        "backend": backend.name,
        "dim": int(next(iter(per_file.values())).shape[1]) if per_file else 0,
        "files_embedded": len(per_file),
        "ms_per_window": float(np.mean(encode_ms)) if encode_ms else None,
        "families": fam_rows,
    }


def summarise(res):
    music = [f for f in res["families"] if not f["synthetic"]]
    syn = [f for f in res["families"] if f["synthetic"]]

    def agg(rows):
        if not rows:
            return None
        return {
            "n_families": len(rows),
            "mean_snr": float(np.mean([r["snr"] for r in rows])),
            "min_snr": float(np.min([r["snr"] for r in rows])),
            "mean_within": float(np.mean([r["within_spread"] for r in rows])),
            "mean_between": float(np.mean([r["between_dist"] for r in rows])),
        }
    return {"music": agg(music), "synthetic": agg(syn)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("captures_dir")
    ap.add_argument("--backends", nargs="+", required=True)
    ap.add_argument("--window", type=float, default=10.0)
    ap.add_argument("--max-windows", type=int, default=4)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    fam = collections.defaultdict(list)
    for n in sorted(os.listdir(args.captures_dir)):
        if n.lower().endswith(AUDIO_EXTS):
            fam[family_key(n)].append(os.path.join(args.captures_dir, n))
    fam = {k: v for k, v in fam.items() if len(v) >= 2}

    all_res = []
    for spec in args.backends:
        kind, _, model_id = spec.partition(":")
        print("\n=== %s: %s ===" % (kind, model_id), flush=True)
        try:
            be = (MertBackend if kind == "mert" else ClapBackend)(model_id, args.device)
            res = evaluate(be, fam, args.window, args.max_windows)
            res["summary"] = summarise(res)
            all_res.append(res)
            s = res["summary"]
            print("  dim=%d files=%d %.0f ms/window"
                  % (res["dim"], res["files_embedded"], res["ms_per_window"]))
            for label in ("music", "synthetic"):
                a = s[label]
                if a:
                    print("  %-9s SNR mean=%.2f min=%.2f  (within=%.4f between=%.4f)"
                          % (label, a["mean_snr"], a["min_snr"],
                             a["mean_within"], a["mean_between"]))
        except Exception as exc:
            print("  FAILED: %s: %s" % (type(exc).__name__, exc))
            all_res.append({"backend": model_id, "error": "%s: %s" % (type(exc).__name__, exc)})

    with open(args.out, "w") as f:
        json.dump(all_res, f, indent=2)
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()

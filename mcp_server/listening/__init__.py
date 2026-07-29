"""Listening Engine — offline perceptual analysis of master-bus captures.

Closes the perception loop: captures produced by ``capture_audio`` go in,
empirical perceptual verdicts come out, in the same canonical snapshot
shape ``evaluate_move`` consumes. Graduated from spikes/listening/ on
2026-07-30 after an adversarially-verified prototype and a user-accepted
live end-to-end pass (capture → move → capture → listen_ab → evaluate_move).
"""

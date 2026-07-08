"""Verification + evaluation harness for the semantic intent router.

Run inside the chatbot container (model is baked into the image):

    docker exec bank-chatbot-api python test_semantic_router.py

Or locally once fastembed + the model are available:

    python test_semantic_router.py

It loads the SemanticIntentRouter, classifies a labelled set of held-out
queries (NOT the training utterances), and reports per-query scores plus
overall accuracy. Use it to tune SEMANTIC_ROUTER_THRESHOLD and the utterances
in app/services/semantic_router/routes.py before enabling "active" mode.
"""

from __future__ import annotations

import sys
from typing import List, Tuple

from app.services.semantic_router import get_semantic_router

# (query, expected_target). Deliberately paraphrased away from the training
# utterances so this measures generalization, not memorization.
LABELLED_QUERIES: List[Tuple[str, str]] = [
    ("annual fee for the platinum card please", "FEE_ENGINE_CARDS"),
    ("how much do you charge to replace a lost debit card", "FEE_ENGINE_CARDS"),
    ("what will it cost to pay off my personal loan ahead of schedule", "FEE_ENGINE_RETAIL_ASSETS"),
    ("processing charge on a car loan", "FEE_ENGINE_RETAIL_ASSETS"),
    ("fee to send money via NPSB on skybanking", "FEE_ENGINE_SKYBANKING"),
    ("skybanking government challan payment charge", "FEE_ENGINE_SKYBANKING"),
    ("closest branch to banani", "LOCATION_SERVICE"),
    ("show me atms around dhanmondi", "LOCATION_SERVICE"),
    ("give me the extension of the IT head", "PHONEBOOK"),
    ("i need the mobile number of the gulshan branch manager", "PHONEBOOK"),
    ("who is currently the managing director", "EBLHOME_LEADERSHIP"),
    ("show the board of directors of the bank", "EBLHOME_LEADERSHIP"),
    ("link for the latest BFIU circular", "EBLHOME_CIRCULARS"),
    ("where do i find bangladesh bank compliance circulars", "EBLHOME_CIRCULARS"),
    ("download islamic banking schedule of charges", "EBLHOME_SOC"),
    ("corporate schedule of charges document", "EBLHOME_SOC"),
    ("credit proposal preparation guide", "EBLHOME_PROPOSALS"),
    ("open the leave application portal for me", "EBLHOME_APPS"),
    ("link to the pay slip system", "EBLHOME_APPS"),
    ("i want to download the account opening form", "EBLHOME_FORMS"),
    ("kyc form file", "EBLHOME_FORMS"),
    ("what's the time right now", "DATETIME"),
    ("today's date?", "DATETIME"),
    ("hello there", "OPENAI_SMALL_TALK"),
    ("thanks for the help", "OPENAI_SMALL_TALK"),
    ("what documents do i need to open a current account", "LIGHTRAG"),
    ("explain the anti money laundering policy", "LIGHTRAG"),
    ("who is the beneficial owner of a limited company", "LIGHTRAG"),
]


def main() -> int:
    router = get_semantic_router()
    if not router.available:
        print("ERROR: semantic router failed to load (fastembed/model unavailable).")
        return 2

    print(f"Model: {router.model_name}  |  threshold: {router.threshold}\n")
    print(f"{'exp':28} {'predicted':22} {'score':>6} {'margin':>6}  ok")
    print("-" * 78)

    correct = 0
    confident = 0
    for query, expected in LABELLED_QUERIES:
        result = router.classify(query)
        predicted = result.target or "(below-threshold)"
        # For accuracy we compare against the top route regardless of threshold,
        # since below-threshold falls back to regex (still measured separately).
        top = max(result.scores_by_route, key=result.scores_by_route.get)
        ok = top == expected
        correct += int(ok)
        confident += int(result.is_confident)
        flag = "OK " if ok else "XX "
        print(
            f"{expected:28} {predicted:22} {result.score:6.3f} {result.margin:6.3f}  {flag}"
            f"  <- {query}"
        )

    total = len(LABELLED_QUERIES)
    print("-" * 78)
    print(f"Top-1 accuracy: {correct}/{total} = {correct / total:.1%}")
    print(f"Confident (>= threshold): {confident}/{total} = {confident / total:.1%}")
    return 0 if correct == total else 1


if __name__ == "__main__":
    sys.exit(main())

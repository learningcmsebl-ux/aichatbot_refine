"""Route definitions for the semantic intent router.

Each key is a routing *target* string that matches the targets produced by
``RoutingEngine.decide`` / consumed by ``ChatOrchestrator`` dispatch, so the
semantic router's output can be mapped 1:1 without translation.

The values are example utterances. The router embeds these once at startup and
classifies an incoming query by cosine similarity to them. To improve routing
accuracy you add/remove example utterances here — no regex, no code changes.

Note: "LIGHTRAG" is the knowledge-base fallback (policy, product, general
banking Q&A). It is also the default when no route clears the confidence
threshold, but including representative utterances helps separate genuine
knowledge questions from phonebook/contact lookups.
"""

from __future__ import annotations

from typing import Dict, List

ROUTE_UTTERANCES: Dict[str, List[str]] = {
    # ---- Card fees / charges (authoritative Fee Engine) ----
    "FEE_ENGINE_CARDS": [
        "what is the annual fee for a platinum credit card",
        "credit card replacement charge",
        "debit card annual fee",
        "card renewal fee",
        "late payment charge on credit card",
        "credit card cash advance fee",
        "how much is the card issuance fee",
        "supplementary card fee",
        "credit card fee schedule",
        "visa signature card charges",
        "card conversion fee",
        "SMS alert charge for card",
    ],
    # ---- Retail asset / loan charges (Fee Engine) ----
    "FEE_ENGINE_RETAIL_ASSETS": [
        "personal loan processing fee",
        "home loan early settlement charge",
        "auto loan prepayment penalty",
        "loan processing charge",
        "what is the fee for closing my personal loan early",
        "retail loan charges",
        "car loan processing fee",
        "loan documentation charge",
    ],
    # ---- Skybanking (mobile app) fees ----
    "FEE_ENGINE_SKYBANKING": [
        "skybanking fund transfer fee",
        "skybanking add money charge",
        "skybanking NPSB transfer fee",
        "skybanking RTGS charge",
        "skybanking a-challan fee",
        "skybanking duplicate pin charge",
        "skybanking statement fee",
        "mobile app transfer charge",
    ],
    # ---- Branch / ATM / location service ----
    "LOCATION_SERVICE": [
        "where is the nearest branch",
        "ATM locations near me",
        "find a branch in gulshan",
        "priority center address",
        "which branches are in dhaka",
        "nearest CRM machine",
        "head office address",
        "branch opening hours and location",
        "list of ATMs in chittagong",
    ],
    # ---- Phonebook / employee contact lookup ----
    # Includes CONTACT queries about senior roles (MD/CEO/CFO/DMD/chairman) so
    # that "phone number of the managing director" routes here, while identity
    # queries ("who is the managing director") stay on EBLHOME_LEADERSHIP.
    "PHONEBOOK": [
        "what is the phone number of john",
        "email address of the branch manager",
        "contact details of the head of IT",
        "find employee extension",
        "ip phone number of rahim",
        "who is the manager of gulshan branch",
        "employee id of karim",
        "staff directory lookup",
        "give me the mobile number of the operations head",
        "phone number of the managing director",
        "contact number of the CEO",
        "email of the deputy managing director",
        "extension of the CFO",
        "how can I contact the head of HR",
        "phone number of the chairman",
        "contact details of the DMD",
        "reach the managing director on phone",
    ],
    # ---- EBL Home: leadership / management profiles ----
    "EBLHOME_LEADERSHIP": [
        "who is the managing director of the bank",
        "who is the managing director",
        "who is the current MD",
        "who is the CEO",
        "name of the managing director",
        "show me the CEO profile",
        "board of directors",
        "list of deputy managing directors",
        "who is the deputy managing director",
        "management team of the bank",
        "who is the chairman",
        "profile of the DMD",
        "senior management photos",
        "tell me about the bank leadership",
    ],
    # ---- EBL Home: compliance circulars ----
    "EBLHOME_CIRCULARS": [
        "BFIU circulars link",
        "bangladesh bank circulars",
        "compliance circular",
        "AOF observations",
        "internal control and compliance circular",
        "regulatory circular link",
        "where can I find the latest circulars",
        "outward clearing circular",
    ],
    # ---- EBL Home: schedule of charges documents ----
    "EBLHOME_SOC": [
        "download the schedule of charges",
        "islamic banking schedule of charges",
        "corporate schedule of charges pdf",
        "retail schedule of charges document",
        "SME schedule of charges",
        "schedule of charges for priority banking",
        "give me the schedule of charges file",
    ],
    # ---- EBL Home: proposal updates / guides ----
    "EBLHOME_PROPOSALS": [
        "credit proposal guide",
        "proposal update document",
        "loan proposal format",
        "download proposal template",
        "proposal writing guideline",
        "latest proposal updates",
    ],
    # ---- EBL Home: app / portal links ----
    "EBLHOME_APPS": [
        "link to the leave application portal",
        "open the HR portal",
        "intranet application link",
        "give me the link to eRequisition",
        "internal app for attendance",
        "portal for pay slip",
        "eblhome application link",
    ],
    # ---- EBL Home: downloadable forms ----
    "EBLHOME_FORMS": [
        "download the account opening form",
        "leave application form",
        "KYC form download",
        "where can I get the loan application form",
        "give me the form for fund transfer",
        "requisition form download",
        "nominee change form",
    ],
    # ---- Date / time ----
    "DATETIME": [
        "what is the time now",
        "what is today's date",
        "what day is it today",
        "current time",
        "what is the date today",
    ],
    # ---- Small talk / greetings ----
    "OPENAI_SMALL_TALK": [
        "hi",
        "hello",
        "how are you",
        "good morning",
        "thanks a lot",
        "thank you",
        "who are you",
        "what can you do",
        "bye",
    ],
    # ---- Knowledge base fallback: policy / product / general banking Q&A ----
    "LIGHTRAG": [
        "what are the features of the savings account",
        "eligibility criteria for a home loan",
        "explain the KYC policy",
        "what is the code of conduct",
        "tell me about the bank's history",
        "what documents are required to open a current account",
        "how does the fixed deposit work",
        "what is the interest rate policy",
        "who is the beneficial owner of a limited company",
        "corporate account opening requirements",
        "what is the leave policy",
        "explain the anti money laundering policy",
    ],
}

# Convenience ordered list of target names.
ROUTE_TARGETS: List[str] = list(ROUTE_UTTERANCES.keys())

"""
ALL ABOUT BRAIN — Real-World Architectural, Urban & Scientific Apparatus Reference Engine (`Rule R72-R`).

Retrieves public-domain / CC-licensed real-world reference photographs from Wikimedia Commons
(`https://commons.wikimedia.org/w/api.php`) across ALL THREE real-world categories:
  1. `institution`: Universities, research institutes, hospitals (`UCL Wilkins Portico`,
     `Harvard Memorial Hall / Sever Hall`, `MIT Great Dome`, `Baylor Pat Neff Hall`,
     `University of Iowa Old Capitol`, `Oxford Radcliffe Camera`, etc.).
  2. `urban_setting`: Real background streets, plazas, subways, footbridges, parks, outdoor markets
     (`Harvard Square`, `Charles River Footbridge`, `London Underground`, `Millennium Bridge`,
     `Outdoor Gourmet Farmers Market`, etc.).
  3. `scientific_apparatus`: Real laboratory instruments & classic psychological rigs
     (`3T MRI Scanner`, `64-Channel EEG Cap`, `Photographic Darkroom Enlarger & Trays`,
     `Robotic Haptic Pantograph Arm`, `Gourmet Jam Tasting Booth`, etc.).

Strict Zero-Pixel-Leak Quarantine Contract (`Rule R72-R`):
  - Raw downloaded photos and sanitized `9:16` structural guides exist EXCLUSIVELY inside
    `/tmp/aab_real_refs/<project_id>/` (strictly outside `WORKSPACE_ROOT`).
  - Only non-pixel metadata, Wikimedia Commons attribution/license records, SHA-256 digests,
    64-bit `dHash` digests, and `27x48` coarse structural gradient vectors are stored inside
    `03_visuals/real_world_refs_manifest.json`.
  - Every Flow-rendered 3D miniature keyframe (`K0 -> K1 -> K2` & `ref_loc_*`) is verified against
    `RQ-Real`:
      * `raw_dhash_distance >= REAL_WORLD_REFS_MIN_DHASH_DISTANCE` (`>= 14` bits: zero pixel copy)
      * `edge_alignment_score >= REAL_WORLD_REFS_MIN_EDGE_ALIGNMENT` (`>= 0.30`: recognizable silhouette)
  - `/tmp/aab_real_refs/<project_id>/` (and any temporary `/tmp/fimg_*.jpg` uploads staged from it)
    are purged automatically in `finally:`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np

from pipeline.config import (
    DEFAULT_CDP_PORT,
    DOSSIERS_DIR,
    EXPRESSIVE_25D_V8_STYLE_PROFILE,
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    PROJECTS_DIR,
    PROMPT_SCHEMA_VERSION_V8,
    REAL_WORLD_REFS_MANIFEST_FILENAME,
    REAL_WORLD_REFS_MIN_DHASH_DISTANCE,
    REAL_WORLD_REFS_MIN_EDGE_ALIGNMENT,
    REAL_WORLD_REFS_QUARANTINE_ROOT,
    REF_IMAGES_DIRNAME,
    WORKSPACE_ROOT,
)
from pipeline.reference_image_qa import _dhash_64, _hamming_hex

WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"
WIKIMEDIA_USER_AGENT = (
    "AllAboutBrainResearchBot/1.0 (https://www.youtube.com/@AllAboutBrainOfficial; "
    "scientific-diorama-structural-reference)"
)

# ------------------------------------------------------------------------------
# 1. Curated Real-World Target Dictionaries (3 Categories: Institution, Urban, Apparatus)
# ------------------------------------------------------------------------------
INSTITUTION_ICONIC_LANDMARK_MAP: dict[str, dict[str, Any]] = {
    "ucl": {
        "target_id": "ucl_wilkins_portico",
        "category": "institution",
        "label": "University College London (UCL) Wilkins Building Portico & Main Quad",
        "queries": [
            "Wilkins Building UCL portico",
            "UCL Main Quad Wilkins Building",
            "University College London portico dome",
        ],
        "aliases": ("ucl", "university college london", "queen square london"),
        "architectural_traits": (
            "iconic pale-limestone ten-column Corinthian portico atop wide grand stone steps, "
            "central green-patina classical dome with lantern, symmetrical Georgian stone wings, "
            "and sunlit gravel Main Quad courtyard"
        ),
        "facade_close_traits": (
            "soaring fluted pale-limestone Corinthian columns, carved classical pediment, "
            "tall multi-pane sash windows flanking the grand stone portico steps"
        ),
    },
    "harvard": {
        "target_id": "harvard_memorial_yard",
        "category": "institution",
        "label": "Harvard University Memorial Hall & Red-Brick Harvard Yard",
        "queries": [
            "Memorial Hall Harvard University",
            "Sever Hall Harvard Yard",
            "Harvard Yard red brick hall",
        ],
        "aliases": ("harvard", "harvard university", "william james hall", "harvard yard"),
        "architectural_traits": (
            "iconic Victorian red-brick and buff-sandstone university hall with pointed Gothic gable arches, "
            "patterned slate mansard roof tower, tall arched multi-pane windows, "
            "and sunlit green Harvard Yard lawn crisscrossed by brick walkways and mature elm trees"
        ),
        "facade_close_traits": (
            "textured red-brick facade with carved sandstone Gothic window arches, "
            "tall leaded multi-pane casement windows, and granite entrance steps framed by campus elms"
        ),
    },
    "mit": {
        "target_id": "mit_great_dome",
        "category": "institution",
        "label": "MIT Great Dome & Killian Court",
        "queries": [
            "MIT Great Dome Killian Court",
            "Maclaurin Buildings MIT dome",
        ],
        "aliases": ("mit", "massachusetts institute of technology"),
        "architectural_traits": (
            "monumental neoclassical limestone colonnade of ten Ionic columns supporting a stepped Pantheon-style "
            "Great Dome rotunda overlooking sunlit grassy Killian Court"
        ),
        "facade_close_traits": (
            "monumental pale-limestone Ionic colonnade, chiseled entablature frieze, and tall grid-paned laboratory windows"
        ),
    },
    "baylor": {
        "target_id": "baylor_pat_neff_hall",
        "category": "institution",
        "label": "Baylor University Pat Neff Hall & Founders Mall",
        "queries": [
            "Pat Neff Hall Baylor University",
            "Baylor University Founders Mall",
        ],
        "aliases": ("baylor", "baylor university"),
        "architectural_traits": (
            "Georgian red-brick university hall crowned by a tall white octagonal bell cupola, "
            "four white Corinthian portico columns, and tree-lined red-brick Founders Mall"
        ),
        "facade_close_traits": (
            "warm Georgian red-brick facade, white stone portico columns, and symmetrical white-trimmed sash windows"
        ),
    },
    "iowa": {
        "target_id": "iowa_old_capitol",
        "category": "institution",
        "label": "University of Iowa Old Capitol & Pentacrest",
        "queries": [
            "Old Capitol Iowa City",
            "University of Iowa Pentacrest",
        ],
        "aliases": ("university of iowa", "iowa city", "pentacrest"),
        "architectural_traits": (
            "Greek Revival buff-limestone hall with four-column Doric portico and gleaming gold dome "
            "set atop sunlit green Pentacrest campus lawn"
        ),
        "facade_close_traits": (
            "buff-limestone Doric portico columns, tall pedimented twelve-pane windows, and stone steps"
        ),
    },
    "oxford": {
        "target_id": "oxford_radcliffe_camera",
        "category": "institution",
        "label": "University of Oxford Radcliffe Camera & Square",
        "queries": [
            "Radcliffe Camera Oxford",
            "Radcliffe Square Oxford",
        ],
        "aliases": ("oxford", "university of oxford"),
        "architectural_traits": (
            "circular Palladian golden-limestone rotunda library with paired Corinthian columns, "
            "balustraded parapet, grand lead dome, and cobblestone square"
        ),
        "facade_close_traits": (
            "curved golden Headington-stone rusticated base, paired Corinthian columns, and arched library windows"
        ),
    },
    "cambridge": {
        "target_id": "cambridge_kings_chapel",
        "category": "institution",
        "label": "University of Cambridge Gothic Court",
        "queries": [
            "Kings College Chapel Cambridge",
            "Trinity College Great Court Cambridge",
        ],
        "aliases": ("university of cambridge", "cambridge university"),
        "architectural_traits": (
            "Perpendicular Gothic pale-limestone collegiate court with octagonal corner turrets, "
            "buttressed stained-glass bays, and manicured emerald quadrangle lawn"
        ),
        "facade_close_traits": (
            "carved pale-limestone Gothic buttresses, tall mullioned windows, and stone Tudor archway"
        ),
    },
    "stanford": {
        "target_id": "stanford_main_quad",
        "category": "institution",
        "label": "Stanford University Sandstone Main Quad",
        "queries": [
            "Stanford University Main Quad arches",
            "Memorial Church Stanford Quad",
        ],
        "aliases": ("stanford", "stanford university"),
        "architectural_traits": (
            "warm golden-buff sandstone Romanesque arcades, red clay mission tile roofs, "
            "and sunlit palm-lined stone courtyard"
        ),
        "facade_close_traits": (
            "carved buff-sandstone Romanesque semicircular arches, short stone columns, and red clay eaves"
        ),
    },
    "yale": {
        "target_id": "yale_harkness_quad",
        "category": "institution",
        "label": "Yale University Collegiate Gothic Quad",
        "queries": [
            "Harkness Tower Yale University",
            "Sterling Memorial Library Yale exterior",
        ],
        "aliases": ("yale", "yale university"),
        "architectural_traits": (
            "Collegiate Gothic grey-stone quadrangle, soaring carved stone spire, "
            "leaded gothic windows, and elm-shaded slate walkways"
        ),
        "facade_close_traits": (
            "textured grey-stone Gothic arches, stone mullions, and recessed oak courtyard doorway"
        ),
    },
    "columbia": {
        "target_id": "columbia_low_library",
        "category": "institution",
        "label": "Columbia University Low Memorial Library & College Walk",
        "queries": [
            "Low Memorial Library Columbia University",
            "Butler Library Columbia University",
        ],
        "aliases": ("columbia", "columbia university"),
        "architectural_traits": (
            "neoclassical Indiana-limestone domed rotunda atop wide tiered granite steps "
            "with ten monumental Ionic columns and brick plaza"
        ),
        "facade_close_traits": (
            "monumental fluted Ionic limestone columns, wide granite steps, and tall bronze-framed windows"
        ),
    },
    "caltech": {
        "target_id": "caltech_beckman_court",
        "category": "institution",
        "label": "Caltech Spanish Colonial Arcade & Reflecting Pool",
        "queries": ["Beckman Institute Caltech", "Athenaeum Caltech"],
        "aliases": ("caltech", "california institute of technology"),
        "architectural_traits": "white Spanish-Revival stucco colonnade, terracotta tile roof, and sunlit reflecting pool courtyard",
        "facade_close_traits": "white stucco arches, wrought-iron lanterns, and tall casement laboratory windows",
    },
    "johns_hopkins": {
        "target_id": "johns_hopkins_gilman_hall",
        "category": "institution",
        "label": "Johns Hopkins Gilman Hall & Brick Quad",
        "queries": ["Gilman Hall Johns Hopkins University", "Johns Hopkins Hospital dome"],
        "aliases": ("johns hopkins", "hopkins"),
        "architectural_traits": "Federal-style red-brick hall with white clock tower, arched central palladian window, and brick quad",
        "facade_close_traits": "red-brick masonry with white marble trim and tall arched multi-pane windows",
    },
    "virginia": {
        "target_id": "uva_rotunda_lawn",
        "category": "institution",
        "label": "University of Virginia Jeffersonian Rotunda & Lawn",
        "queries": ["Rotunda University of Virginia", "Academical Village UVA"],
        "aliases": ("university of virginia", "charlottesville"),
        "architectural_traits": "red-brick Jeffersonian domed Rotunda with white Corinthian columns facing terraced green Lawn",
        "facade_close_traits": "red-brick curved wall, white marble Corinthian capitals, and white multi-pane windows",
    },
    "princeton": {
        "target_id": "princeton_nassau_hall",
        "category": "institution",
        "label": "Princeton University Nassau Hall",
        "queries": ["Nassau Hall Princeton University", "Blair Arch Princeton"],
        "aliases": ("princeton", "princeton university"),
        "architectural_traits": "historic sandstone Georgian hall with white belfry cupola and ivy-draped stone lawn",
        "facade_close_traits": "rough-cut golden-brown sandstone masonry, central pediment, and white sash windows",
    },
    "berkeley": {
        "target_id": "berkeley_sather_tower",
        "category": "institution",
        "label": "UC Berkeley Sather Tower Campanile & Memorial Glade",
        "queries": ["Sather Tower UC Berkeley", "Doe Library UC Berkeley"],
        "aliases": ("uc berkeley", "university of california berkeley", "berkeley"),
        "architectural_traits": "pale-granite Venetian campanile clock tower rising above classical white libraries and green glade",
        "facade_close_traits": "white granite neoclassical library facade, tall arched windows, and stone balustrade",
    },
}

URBAN_LANDMARK_QUERY_MAP: dict[str, dict[str, Any]] = {
    "london_eye_thames_wheel": {
        "target_id": "london_eye_thames_wheel",
        "category": "urban_setting",
        "label": "London Eye Cantilevered Observation Wheel & River Thames Embankment",
        "queries": [
            "London Eye River Thames embankment",
            "London Eye observation wheel South Bank",
        ],
        "aliases": ("london eye", "south bank wheel", "thames observation wheel"),
        "architectural_traits": (
            "giant white cantilevered London Eye observation wheel with glass passenger capsules "
            "rising beside the sunlit Portland-stone River Thames embankment and Westminster skyline"
        ),
    },
    "london_red_bus_stop_roundel": {
        "target_id": "london_red_bus_stop_roundel",
        "category": "urban_setting",
        "label": "London Iconic Red Bus Stop Flag Post, Glass Shelter & Double-Decker Bus Lane",
        "queries": [
            "London bus stop roundel red bus",
            "Red double-decker bus stop London street",
        ],
        "aliases": ("london bus stop", "red bus stop roundel", "london bus lane"),
        "architectural_traits": (
            "iconic London red-and-white circular bus stop flag post, modern glass curbside shelter, "
            "and bright red double-decker bus aligned along a straight Portland-stone London avenue"
        ),
    },
    "harvard_square": {
        "target_id": "harvard_square_crosswalk",
        "category": "urban_setting",
        "label": "Harvard Square Cambridge Red-Brick Plaza & Crosswalk",
        "queries": [
            "Harvard Square Cambridge Massachusetts",
            "Harvard Square subway kiosk brick",
        ],
        "aliases": ("harvard square", "cambridge street", "brattle street"),
        "architectural_traits": (
            "sunlit red-brick Cambridge plaza, curved vintage transit headhouse pavilion, "
            "crisp white-striped crosswalk, three-story historic red-brick storefronts, and leafy street trees"
        ),
    },
    "charles_river_bridge": {
        "target_id": "charles_river_footbridge",
        "category": "urban_setting",
        "label": "John W. Weeks Footbridge over the Charles River",
        "queries": [
            "John W Weeks Bridge Harvard",
            "Weeks Footbridge Charles River",
        ],
        "aliases": ("charles river", "weeks footbridge", "river footbridge", "boston river bridge"),
        "architectural_traits": (
            "graceful red-brick and pale-limestone arched pedestrian footbridge spanning sparkling blue river water "
            "with tree-lined riverbanks and university bell towers in the background"
        ),
    },
    "campus_courtyard_steps": {
        "target_id": "harvard_yard_courtyard_steps",
        "category": "urban_setting",
        "label": "University Red-Brick Courtyard Steps & Elm Walkway",
        "queries": [
            "Sever Hall Harvard Yard",
            "Harvard Yard brick walkway trees",
        ],
        "aliases": ("courtyard steps", "campus quad", "brick courtyard"),
        "architectural_traits": (
            "wide granite entrance steps against a warm red-brick academic facade, "
            "flanked by black iron railings, tall deciduous elm canopies, and diagonal red-brick quad paths"
        ),
    },
    "outdoor_farmers_market": {
        "target_id": "outdoor_gourmet_market_pavilion",
        "category": "urban_setting",
        "label": "Sunlit Outdoor Gourmet Farmers Market Pavilion",
        "queries": [
            "Farmers market wooden stall",
            "Outdoor market canopy stalls",
        ],
        "aliases": ("farmers market", "gourmet market", "outdoor market", "tasting pavilion"),
        "architectural_traits": (
            "sunlit open-air timber market pavilion with cream-and-sage canvas awning, "
            "stepped oak tasting counters, brick pedestrian promenade, and dappled park trees"
        ),
    },
    "london_underground": {
        "target_id": "london_underground_platform",
        "category": "urban_setting",
        "label": "London Underground Ceramic-Tiled Station Platform",
        "queries": [
            "London Underground station platform",
            "Tube station platform tiles London",
        ],
        "aliases": ("london underground", "tube platform", "subway platform"),
        "architectural_traits": (
            "curved cream-and-cobalt ceramic tunnel wall tiles, crisp yellow platform safety line, "
            "arched underground concourse lighting, and silver commuter rail car"
        ),
    },
    "millennium_bridge": {
        "target_id": "london_millennium_bridge",
        "category": "urban_setting",
        "label": "London Millennium Pedestrian Suspension Bridge",
        "queries": ["Millennium Bridge London", "Millennium Footbridge Thames"],
        "aliases": ("millennium bridge", "thames footbridge"),
        "architectural_traits": (
            "sleek steel lateral-suspension pedestrian footbridge spanning wide river water "
            "aligned on axis with a classical stone cathedral dome"
        ),
    },
    "central_park": {
        "target_id": "urban_tree_lined_park_walkway",
        "category": "urban_setting",
        "label": "Sunlit Tree-Lined City Park Mall & Benches",
        "queries": ["The Mall Central Park trees", "City park tree lined promenade"],
        "aliases": ("central park", "city park walkway", "park promenade"),
        "architectural_traits": (
            "wide sunlit promenade framed by a double colonnade of tall elm canopies, "
            "cast-iron wood-slat park benches, and distant city skyline rooftops"
        ),
    },
}

SCIENTIFIC_APPARATUS_QUERY_MAP: dict[str, dict[str, Any]] = {
    "darkroom_enlarger": {
        "target_id": "harvard_darkroom_enlarger_rig",
        "category": "scientific_apparatus",
        "label": "Optical Photographic Darkroom Enlarger & Silver-Gelatin Developing Trays",
        "queries": [
            "Photographic enlarger darkroom",
            "Darkroom developing trays prints",
        ],
        "aliases": ("darkroom", "enlarger", "photography course", "developing tray", "photo print"),
        "architectural_traits": (
            "classic vertical-column optical condenser enlarger over a wooden easel, "
            "three white porcelain developing trays on a wet bench, and overhead cord with wooden clips "
            "holding black-and-white landscape photographs under warm amber-and-tungsten studio light"
        ),
    },
    "gourmet_jam_tasting_booth": {
        "target_id": "gourmet_jam_tasting_display",
        "category": "scientific_apparatus",
        "label": "24-Jar vs 6-Jar Gourmet Fruit Preserve Tasting Display",
        "queries": [
            "Jam jars display market",
            "Fruit preserves glass jars row",
        ],
        "aliases": ("jam jar", "tasting booth", "24 jam", "6 jam", "preserve jars"),
        "architectural_traits": (
            "tiered natural-oak tasting booth counter neatly arranged with rows of faceted clear glass "
            "fruit-preserve jars topped with brass lids, ruby-berry and apricot colors, and small ceramic sample spoons"
        ),
    },
    "mri_scanner": {
        "target_id": "clinical_3t_mri_scanner",
        "category": "scientific_apparatus",
        "label": "Clinical 3T MRI Scanner Bore & Observation Suite",
        "queries": ["MRI scanner medical", "Magnetic resonance imaging scanner"],
        "aliases": ("mri", "fmri", "scanner bore"),
        "architectural_traits": (
            "cylindrical matte-white 3T MRI magnet gantry with circular bore, motorized cushioned table, "
            "and wide acoustic control-room observation window"
        ),
    },
    "eeg_cap": {
        "target_id": "high_density_eeg_cap_rig",
        "category": "scientific_apparatus",
        "label": "64-Channel EEG Electrode Cap & Amplifier Console",
        "queries": ["EEG cap electrodes", "Electroencephalography cap"],
        "aliases": ("eeg", "electrode cap", "polysomnography"),
        "architectural_traits": (
            "structured 64-node sensor cap with neat ribbon leads routed to a brushed-aluminum amplifier console"
        ),
    },
    "robot_pantograph": {
        "target_id": "robotic_haptic_pantograph_rig",
        "category": "scientific_apparatus",
        "label": "Dual-Pedestal Robotic Pantograph Linkage Arm",
        "queries": ["Phantom haptic device", "Pantograph mechanism"],
        "aliases": ("pantograph", "tickle robot", "robotic arm rig"),
        "architectural_traits": (
            "precision brushed-aluminum articulated pantograph linkage arm bridging left hand dial and right foam stylus"
        ),
    },
    "two_room_shoebox_testing_rig": {
        "target_id": "two_room_shoebox_testing_rig",
        "category": "scientific_apparatus",
        "label": "Two-Room Cognitive Psychology Testing Suite with Oak Doorframe, White Shoeboxes & Colored Wooden Blocks",
        "queries": ["Wooden building blocks", "Wooden toy blocks", "Cardboard box table"],
        "aliases": ("shoebox", "wooden blocks", "doorway experiment"),
        "architectural_traits": (
            "clean high-key sunlit psychology testing suite divided by a crisp solid oak doorframe "
            "between wooden tables holding white cardboard shoeboxes and crimson and cobalt wooden blocks"
        ),
    },
}

NEUROANATOMY_CUTAWAY_MAP: dict[str, dict[str, Any]] = {
    "hippocampus": {
        "target_id": "neuro_cutaway_hippocampus",
        "category": "neuroanatomy_plate",
        "label": "Human Hippocampus Inferolateral & Coronal Cutaway Plate",
        "required_viewpoint": "inferior_lateral_cutaway",
        "forbidden_viewpoints": ("dorsal_callosum", "corpus_callosum_highlight", "dorsal_top_down"),
        "verified_commons_titles": (
            "File:Hippocampus image.png",
            "File:202102 Frontal plane of the brain hippocampus.svg",
            "File:Human brain frontal (coronal) section.JPG",
        ),
        "queries": [
            "Hippocampus image BodyParts3D",
            "Human brain frontal coronal section",
        ],
        "aliases": ("hippocampus", "posterior hippocampus", "anterior hippocampus", "hippocampal"),
        "architectural_traits": (
            "oblique inferolateral temporal cutaway exposing the deep ventral C-curved hippocampus tucked well below "
            "the dorsal corpus callosum arch"
        ),
    },
    "thalamus_brainstem_csf": {
        "target_id": "neuro_cutaway_thalamus_brainstem_csf",
        "category": "neuroanatomy_plate",
        "label": "Midsagittal Thalamus, Brainstem & Ventricular CSF System Plate",
        "required_viewpoint": "midsagittal_cutaway",
        "forbidden_viewpoints": ("lateral_cortical_surface", "lateral_surface"),
        "verified_commons_titles": (
            "File:Thalamus.png",
            "File:Brainstem.png",
            "File:Human ventricular system -- left side view.png",
        ),
        "queries": [
            "Thalamus BodyParts3D",
            "Brainstem BodyParts3D",
            "Human ventricular system left side view",
        ],
        "aliases": ("thalamus", "brainstem", "locus coeruleus", "pons", "ventricular", "csf", "glymphatic"),
        "architectural_traits": (
            "clean midsagittal cutaway exposing midline diencephalic thalamus perched atop the brainstem column "
            "and surrounding cerebral ventricular CSF channels"
        ),
    },
    "insula": {
        "target_id": "neuro_cutaway_insula_operculum",
        "category": "neuroanatomy_plate",
        "label": "Lateral Sylvian Operculum-Retracted Insular Cortex Plate",
        "required_viewpoint": "lateral_opercular_retracted",
        "forbidden_viewpoints": ("midsagittal", "midsagittal_cutaway", "sagittal_midline"),
        "verified_commons_titles": (
            "File:Brain lobes - insular lobe.png",
            "File:Human brain view on transverse temporal and insular gyri.JPG",
            "File:Gray731.png",
        ),
        "queries": [
            "Brain lobes insular lobe",
            "Human brain view on transverse temporal and insular gyri",
        ],
        "aliases": ("insula", "insular cortex", "anterior insula", "posterior insula", "insula fold"),
        "architectural_traits": (
            "lateral hemisphere view with the frontoparietal and temporal opercula retracted along the Sylvian fissure "
            "to reveal the buried short and long insular gyri"
        ),
    },
    "prefrontal_cortex": {
        "target_id": "neuro_cutaway_prefrontal_cortex",
        "category": "neuroanatomy_plate",
        "label": "Three-Quarter Anterolateral Prefrontal Cortex Plate",
        "required_viewpoint": "anterior_three_quarter_lateral",
        "forbidden_viewpoints": (),
        "verified_commons_titles": (
            "File:Prefrontal cortex (left) - lateral view.png",
            "File:Prefrontal cortex (left) - anterior view.png",
            "File:Cerebrum - frontal lobe - anterior view.png",
        ),
        "queries": [
            "Prefrontal cortex left lateral view",
            "Prefrontal cortex left anterior view",
        ],
        "aliases": ("prefrontal cortex", "dorsolateral prefrontal cortex", "ventromedial prefrontal cortex", "dlpfc", "vmpfc"),
        "architectural_traits": (
            "three-quarter anterolateral view of the rostral frontal pole and dorsolateral prefrontal gyri"
        ),
    },
}

_SKIP_COMMONS_TITLE_TOKENS: tuple[str, ...] = (
    "logo",
    "coat of arms",
    "shield",
    "seal",
    "map",
    "diagram",
    "chart",
    "graph",
    "portrait",
    "headshot",
    "signature",
    "plaque",
    "stamp",
    "icon",
    "flag",
    "fema",
    "hurricane",
    "katrina",
    "tornado",
    "earthquake",
    "tsunami",
    "disaster",
    "destroyed",
    "demolished",
    "abandoned",
    "dilapidated",
    "wreckage",
    "demolition",
    "waarschuwing",
    "anno domini",
    "ndc ",
    "mg bottle",
    "rx only",
    "zydus",
    "pfizer",
    "novartis",
    "sandoz",
    "truvada",
    "adderall",
    "ibuprofen",
    "nateglinide",
    "alphabet",
    "letter blocks",
    "digifoto",
    "postcard",
    "xylografi",
    ".svg",
    ".pdf",
    ".tif",
    ".djvu",
    ".webm",
    ".ogv",
)

_BANNED_COMMONS_CONTENT_RE = re.compile(
    r"\b(?:fema|hurricane|katrina|tornado|flood(?:ed|ing)?|earthquake|tsunami|disaster|"
    r"damag(?:e|ed)|destroy(?:ed)?|demolish(?:ed|ing)?|demolition|ruins?|abandoned|dilapidated|"
    r"wreck(?:age|ed)?|war|bomb(?:ed|ing)?|protest|riot|fire|burned|collaps(?:e|ed)|"
    r"waarschuwing\w*|warning(?:\s+sign)?|caution|danger|hazard|poster|signage|anno\s+domini|"
    r"ndc\s*\d+|mg\s+bottle|pill\s+bottle|prescription\s+bottle|tablets|rx\s+only|zydus|nateglinide|alphabet|letter\s+blocks|"
    r"digifoto|postcard|xylografi|emergency|labeled)\b",
    flags=re.IGNORECASE,
)


def is_commons_candidate_blocked(
    title: str,
    extmetadata: dict[str, Any] | None = None,
    *,
    allow_neuroanatomy_diagram: bool = False,
) -> tuple[bool, str]:
    """
    R85 Reference Content Blocklist: Rejects disaster/FEMA/hurricane/damage/ruin/warning-sign/Rx-label/alphabet-block
    photographs across BOTH file title and Wikimedia `extmetadata` (`ImageDescription`, `ObjectName`, `Categories`).
    """
    t_low = str(title or "").lower()
    for bad in _SKIP_COMMONS_TITLE_TOKENS:
        if allow_neuroanatomy_diagram and bad in ("diagram", ".svg", "label", "anatomy"):
            continue
        if bad == "graph":
            if re.search(r"\bgraph\b", t_low):
                return True, "blocked_title_token:graph"
            continue
        if bad in t_low:
            return True, f"blocked_title_token:{bad}"
    m_title = _BANNED_COMMONS_CONTENT_RE.search(str(title or ""))
    if m_title:
        return True, f"blocked_title_regex:{m_title.group(0).lower()}"
    if isinstance(extmetadata, dict) and extmetadata:
        meta_parts: list[str] = []
        for mk in ("ImageDescription", "ObjectName", "Categories", "Credit"):
            raw_v = str((extmetadata.get(mk) or {}).get("value") or "")
            if raw_v:
                meta_parts.append(re.sub(r"<[^>]+>", " ", raw_v))
        meta_txt = " ".join(meta_parts)
        m_meta = _BANNED_COMMONS_CONTENT_RE.search(meta_txt)
        if m_meta:
            return True, f"blocked_extmetadata:{m_meta.group(0).lower()}"
    return False, ""


def _safe_slug(token: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(token or "").strip()).strip("_") or "default_project"


def _bgr_dhash64(bgr: np.ndarray) -> tuple[str, int]:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    dh_hex = str(_dhash_64(gray))
    return dh_hex, int(dh_hex, 16)


def ensure_quarantine_dir(project_id: str, quarantine_root: Path | None = None) -> Path:
    """
    Returns `/tmp/aab_real_refs/<project_id>` and strictly refuses any path inside `WORKSPACE_ROOT`.
    """
    root = Path(quarantine_root) if quarantine_root is not None else Path(REAL_WORLD_REFS_QUARANTINE_ROOT)
    q_dir = (root / _safe_slug(project_id)).resolve()
    ws_resolved = Path(WORKSPACE_ROOT).resolve()
    if q_dir == ws_resolved or q_dir.is_relative_to(ws_resolved):
        raise ValueError(
            f"[R72-R] Quarantine directory {q_dir} MUST reside outside WORKSPACE_ROOT ({ws_resolved})!"
        )
    (q_dir / "raw").mkdir(parents=True, exist_ok=True)
    (q_dir / "guides").mkdir(parents=True, exist_ok=True)
    return q_dir


def purge_real_world_quarantine(
    project_id: str,
    quarantine_root: Path | None = None,
    staged_guide_sha6_set: set[str] | None = None,
) -> dict[str, Any]:
    """
    Deletes `/tmp/aab_real_refs/<project_id>` and any `/tmp/fimg_<sha6>.jpg` temporary upload files
    staged from quarantined structural guides so ZERO third-party pixels remain on disk.
    """
    root = Path(quarantine_root) if quarantine_root is not None else Path(REAL_WORLD_REFS_QUARANTINE_ROOT)
    q_dir = (root / _safe_slug(project_id)).resolve()
    ws_resolved = Path(WORKSPACE_ROOT).resolve()
    if q_dir == ws_resolved or q_dir.is_relative_to(ws_resolved):
        raise ValueError(f"[R72-R] Refusing to purge path inside WORKSPACE_ROOT: {q_dir}")

    collected_sha6: set[str] = set(staged_guide_sha6_set or set())
    if q_dir.exists():
        for f in q_dir.rglob("*"):
            if f.is_file():
                try:
                    collected_sha6.add(hashlib.sha1(f.read_bytes()).hexdigest()[:6])
                except Exception:
                    pass
        shutil.rmtree(q_dir, ignore_errors=True)

    tmp_dir = Path(tempfile.gettempdir())
    removed_staged: list[str] = []
    for sha6 in collected_sha6:
        cand_jpg = tmp_dir / f"fimg_{sha6}.jpg"
        if cand_jpg.exists():
            try:
                cand_jpg.unlink()
                removed_staged.append(cand_jpg.name)
            except Exception:
                pass

    return {
        "project_id": _safe_slug(project_id),
        "quarantine_dir": str(q_dir),
        "purged": not q_dir.exists(),
        "removed_staged_uploads": removed_staged,
    }


def resolve_real_world_target_spec(key_or_text: str, fallback_category: str = "institution") -> dict[str, Any]:
    """
    Resolves a shorthand key (`'ucl'`, `'harvard'`, `'harvard_square'`, `'darkroom_enlarger'`, etc.)
    or free-text phrase into a normalized `R72-R` target specification dict across all 3 categories.
    """
    raw = str(key_or_text or "").strip()
    low = raw.lower()
    slug_k = re.sub(r"[^a-z0-9_]+", "_", low).strip("_")

    all_registries = (
        INSTITUTION_ICONIC_LANDMARK_MAP,
        URBAN_LANDMARK_QUERY_MAP,
        SCIENTIFIC_APPARATUS_QUERY_MAP,
        NEUROANATOMY_CUTAWAY_MAP,
    )
    # Pass 1: Exact registry key or exact target_id match across all 3 categories
    for registry in all_registries:
        if slug_k in registry:
            return dict(registry[slug_k])
        for spec in registry.values():
            if str(spec.get("target_id") or "").strip().lower() == slug_k:
                return dict(spec)

    # Pass 2: Longest alias / key substring match so specific phrases ('harvard square') beat broader prefixes ('harvard')
    best_spec: dict[str, Any] | None = None
    best_match_len = 0
    for registry in all_registries:
        for reg_key, spec in registry.items():
            rk_norm = reg_key.lower().replace("_", " ")
            candidates_tok = [reg_key.lower(), rk_norm] + [str(a).lower() for a in (spec.get("aliases") or ())]
            for tok in candidates_tok:
                if tok and (tok in low or tok in slug_k) and len(tok) > best_match_len:
                    best_match_len = len(tok)
                    best_spec = spec
    if best_spec is not None:
        return dict(best_spec)

    return {
        "target_id": slug_k[:40] or "custom_real_world_ref",
        "category": fallback_category,
        "label": raw or "Iconic Architectural Landmark",
        "queries": [raw] if raw else ["University classical brick building courtyard"],
        "aliases": (low,) if low else (),
        "architectural_traits": (
            f"recognizable real-world architectural proportions and material palette of {raw}"
            if raw
            else "recognizable classical brick-and-stone university architecture surrounded by sunlit trees"
        ),
        "facade_close_traits": (
            f"detailed front facade columns, windows, and masonry of {raw}"
            if raw
            else "detailed front masonry facade and tall multi-pane windows"
        ),
    }


def extract_episode_real_world_targets(
    dossier: dict[str, Any] | Path | str | None = None,
    visual_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Extracts real-world targets across ALL THREE categories (`institution`, `urban_setting`,
    `scientific_apparatus`) from an episode's dossier and/or `visual_plan.json`.
    """
    plan = visual_plan if isinstance(visual_plan, dict) else {}
    explicit_targets = plan.get("real_world_targets")
    resolved: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _add(spec_in: dict[str, Any]) -> None:
        tid = str(spec_in.get("target_id") or "").strip()
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            resolved.append(spec_in)

    if isinstance(explicit_targets, list):
        for item in explicit_targets:
            if isinstance(item, str) and item.strip():
                _add(resolve_real_world_target_spec(item))
            elif isinstance(item, dict):
                base = resolve_real_world_target_spec(
                    str(item.get("key") or item.get("target_id") or item.get("query") or item.get("label") or ""),
                    fallback_category=str(item.get("category") or "institution"),
                )
                merged = {**base, **{k: v for k, v in item.items() if v is not None}}
                if item.get("query") and not item.get("queries"):
                    merged["queries"] = [str(item["query"])] + list(base.get("queries") or [])
                _add(merged)

    # Scan dossier + visual_plan text corpus for automatic multi-category discovery
    corpus_parts: list[str] = [
        str(plan.get("dossier_slug") or plan.get("dossier") or ""),
        str(plan.get("real_environment") or ""),
        str(plan.get("primary_institution") or ""),
    ]
    for anc in plan.get("reference_anchors") or []:
        if isinstance(anc, dict) and anc.get("real_world_target_id"):
            _add(
                resolve_real_world_target_spec(
                    str(anc["real_world_target_id"]),
                    fallback_category=str(anc.get("real_world_category") or "institution"),
                )
            )
    for c in plan.get("clips") or []:
        if isinstance(c, dict):
            corpus_parts.append(str(c.get("environment") or ""))
            corpus_parts.append(str(c.get("location_id") or ""))
            corpus_parts.append(str(c.get("action") or ""))
            if c.get("real_world_target_id"):
                _add(resolve_real_world_target_spec(str(c["real_world_target_id"])))

    if isinstance(dossier, (str, Path)):
        d_path = Path(dossier)
        if not d_path.exists() and (Path(DOSSIERS_DIR) / str(dossier)).exists():
            d_path = Path(DOSSIERS_DIR) / str(dossier)
        if d_path.is_dir():
            for fname in ("00_topic.json", "01_sources.json", "02_core_facts.json", "03_story_synthesis.md", "05_iconic_scene.json"):
                fp = d_path / fname
                if fp.exists():
                    try:
                        corpus_parts.append(fp.read_text(encoding="utf-8")[:6000])
                    except Exception:
                        pass
    elif isinstance(dossier, dict):
        corpus_parts.append(json.dumps(dossier, ensure_ascii=False)[:6000])

    corpus_low = " ".join(corpus_parts).lower()
    for registry in (INSTITUTION_ICONIC_LANDMARK_MAP, URBAN_LANDMARK_QUERY_MAP, SCIENTIFIC_APPARATUS_QUERY_MAP):
        for _, spec in registry.items():
            if any(alias in corpus_low for alias in (spec.get("aliases") or ())):
                _add(dict(spec))

    return resolved


def fetch_wikimedia_commons_reference(
    queries: str | list[str],
    quarantine_dir: Path,
    target_id: str = "landmark",
    timeout_sec: float = 20.0,
    *,
    allow_neuroanatomy_diagram: bool = False,
) -> dict[str, Any]:
    """
    Searches Wikimedia Commons (`https://commons.wikimedia.org/w/api.php`) using compliant `User-Agent`
    headers, downloads the best high-resolution public photograph strictly into
    `<quarantine_dir>/raw/<target_id>.jpg`, and returns metadata + hashes.
    """
    q_dir = Path(quarantine_dir).resolve()
    ws_resolved = Path(WORKSPACE_ROOT).resolve()
    if q_dir == ws_resolved or q_dir.is_relative_to(ws_resolved):
        raise ValueError(f"[R72-R] Raw Wikimedia download refused inside WORKSPACE_ROOT: {q_dir}")

    raw_dir = q_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    q_list = [queries] if isinstance(queries, str) else [str(q).strip() for q in queries if str(q).strip()]

    candidates: list[dict[str, Any]] = []
    for q_str in q_list:
        if q_str.lower().startswith("file:"):
            params = {
                "action": "query",
                "titles": q_str,
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": "1280",
                "format": "json",
            }
        else:
            params = {
                "action": "query",
                "generator": "search",
                "gsrnamespace": "6",
                "gsrsearch": f"{q_str} filetype:bitmap",
                "gsrlimit": "10",
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": "1280",
                "format": "json",
            }
        url = f"{WIKIMEDIA_API_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": WIKIMEDIA_USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue

        pages = (payload.get("query") or {}).get("pages") or {}
        for _, page in pages.items():
            title = str(page.get("title") or "")
            iinfo_list = page.get("imageinfo") or []
            ext_pre = (iinfo_list[0].get("extmetadata") or {}) if iinfo_list else {}
            blocked_cand, _ = is_commons_candidate_blocked(
                title, ext_pre, allow_neuroanatomy_diagram=allow_neuroanatomy_diagram
            )
            if blocked_cand:
                continue
            if not iinfo_list:
                continue
            ii = iinfo_list[0]
            mime = str(ii.get("mime") or "").lower()
            if mime not in ("image/jpeg", "image/png", "image/webp", "image/svg+xml"):
                continue
            w = int(ii.get("width") or 0)
            h = int(ii.get("height") or 0)
            if mime != "image/svg+xml" and (w < 480 or h < 340):
                continue
            dl_url = str(ii.get("thumburl") or (ii.get("url") if mime != "image/svg+xml" else "") or "").strip()
            if not dl_url:
                continue
            ext = ii.get("extmetadata") or {}
            lic_short = str((ext.get("LicenseShortName") or {}).get("value") or "Wikimedia Commons").strip()
            artist_raw = str((ext.get("Artist") or {}).get("value") or "").strip()
            artist_clean = re.sub(r"<[^>]+>", "", artist_raw).strip()[:120]
            # Prefer horizontal/architectural framing with generous resolution
            res_score = min(w, 2400) * min(h, 1800) / 1_000_000.0
            aspect = w / float(max(h, 1))
            arch_bonus = 1.25 if 0.65 <= aspect <= 2.1 else 0.75
            candidates.append(
                {
                    "query_used": q_str,
                    "commons_title": title,
                    "commons_page_url": str(ii.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}"),
                    "download_url": dl_url,
                    "orig_width": w,
                    "orig_height": h,
                    "mime": mime,
                    "license": lic_short,
                    "artist": artist_clean,
                    "score": round(res_score * arch_bonus, 4),
                }
            )
        if candidates:
            break

    if not candidates:
        raise RuntimeError(f"[R72-R] Wikimedia Commons returned zero valid bitmap candidates for queries={q_list!r}")

    candidates.sort(key=lambda c: float(c["score"]), reverse=True)
    last_err = ""
    for cand in candidates[:5]:
        try:
            dl_req = urllib.request.Request(cand["download_url"], headers={"User-Agent": WIKIMEDIA_USER_AGENT})
            with urllib.request.urlopen(dl_req, timeout=timeout_sec) as resp:
                img_bytes = resp.read()
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None or bgr.size == 0:
                continue
            out_raw = raw_dir / f"{_safe_slug(target_id)}.jpg"
            cv2.imwrite(str(out_raw), bgr, [cv2.IMWRITE_JPEG_QUALITY, 94])
            raw_sha256 = hashlib.sha256(out_raw.read_bytes()).hexdigest()
            raw_dh_hex, raw_dh_int = _bgr_dhash64(bgr)
            return {
                "ok": True,
                "target_id": target_id,
                "raw_path": str(out_raw),
                "raw_sha256": raw_sha256,
                "raw_dhash64_int": raw_dh_int,
                "raw_dhash64_hex": raw_dh_hex,
                "commons_title": cand["commons_title"],
                "commons_page_url": cand["commons_page_url"],
                "license": cand["license"],
                "artist": cand["artist"],
                "query_used": cand["query_used"],
                "downloaded_shape": [int(bgr.shape[1]), int(bgr.shape[0])],
                "research_visual_signoff_required": True,
                "research_visual_approved": None,
            }
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            continue

    raise RuntimeError(f"[R72-R] Failed to download Wikimedia Commons image for {target_id}: {last_err}")


def compute_coarse_structural_edge_vector(bgr: np.ndarray, grid_wh: tuple[int, int] = (27, 48)) -> list[float]:
    """
    Computes a normalized `27x48` coarse structural Sobel gradient magnitude vector (`L2`-normalized)
    capturing macro architectural roof/dome/column/horizon massing while ignoring fine photographic grain.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (grid_wh[0] * 4, grid_wh[1] * 4), interpolation=cv2.INTER_AREA)
    smooth = cv2.GaussianBlur(small, (7, 7), 1.8)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    pooled = cv2.resize(mag, grid_wh, interpolation=cv2.INTER_AREA).flatten().astype(np.float64)
    norm = float(np.linalg.norm(pooled))
    if norm <= 1e-8:
        return [0.0] * int(grid_wh[0] * grid_wh[1])
    return [round(float(v / norm), 6) for v in pooled]


def build_sanitized_9x16_structural_guide(
    raw_path: str | Path,
    guide_path: str | Path,
    target_wh: tuple[int, int] = (1080, 1920),
) -> dict[str, Any]:
    """
    Sanitizes a quarantined real-world reference photo inside `/tmp/aab_real_refs/<project_id>/`:
      1. Blurs/inpaints any incidental human faces (via `detect_human_faces_yunet`) and bottom-corner watermarks.
      2. Scrubs photographic sensor grain via bilateral abstraction so raw textures are not copied.
      3. Expands landscape (`4:3` / `3:2`) building facades into full-bleed `1080x1920` (`9:16`) vertical framing
         with seamless atmospheric sky dome extension above and courtyard/ground extension below (preserving full
         building colonnade/roof width with ZERO black bars!).
    """
    from pipeline.source_reenactment import detect_human_faces_yunet

    rp = Path(raw_path).resolve()
    gp = Path(guide_path).resolve()
    ws_resolved = Path(WORKSPACE_ROOT).resolve()
    if gp == ws_resolved or gp.is_relative_to(ws_resolved):
        raise ValueError(f"[R72-R] Refusing to write structural guide inside WORKSPACE_ROOT: {gp}")

    bgr = cv2.imread(str(rp), cv2.IMREAD_COLOR)
    if bgr is None or bgr.size == 0:
        raise RuntimeError(f"[R72-R] Unable to decode raw reference image: {rp}")

    img = bgr.copy()
    h, w = img.shape[:2]

    # 1. Blur any incidental pedestrians / faces
    faces = detect_human_faces_yunet(img, score_threshold=0.42)
    for fx, fy, fw, fh, _ in faces:
        x0, y0 = max(0, fx - fw // 4), max(0, fy - fh // 4)
        x1, y1 = min(w, fx + fw + fw // 4), min(h, fy + fh + fh // 4)
        if x1 > x0 + 4 and y1 > y0 + 4:
            img[y0:y1, x0:x1] = cv2.GaussianBlur(img[y0:y1, x0:x1], (45, 45), 0)

    # 2. Soft-mask bottom 4% strip against any photographer corner watermark
    wm_y0 = max(0, int(round(h * 0.96)))
    if h - wm_y0 >= 4:
        img[wm_y0:h, :] = cv2.GaussianBlur(img[wm_y0:h, :], (31, 31), 0)

    # 3. Bilateral color abstraction (scrubs photographic film/sensor pixel grain while keeping architectural edges)
    work_max = 960
    sc0 = min(1.0, work_max / float(max(h, w)))
    work = cv2.resize(img, (max(32, int(round(w * sc0))), max(32, int(round(h * sc0)))), interpolation=cv2.INTER_AREA)
    for _ in range(2):
        work = cv2.bilateralFilter(work, d=9, sigmaColor=42, sigmaSpace=18)

    wh, ww = work.shape[:2]
    dst_w, dst_h = int(target_wh[0]), int(target_wh[1])
    src_ar = ww / float(max(wh, 1))
    dst_ar = dst_w / float(dst_h)

    if src_ar <= dst_ar * 1.18:
        # Already vertical or near-vertical -> clean center crop to 9:16
        if src_ar > dst_ar:
            cw = max(1, int(round(wh * dst_ar)))
            x0 = (ww - cw) // 2
            cropped = work[:, x0 : x0 + cw]
        else:
            ch = max(1, int(round(ww / dst_ar)))
            y0 = (wh - ch) // 2
            cropped = work[y0 : y0 + ch, :]
        canvas = cv2.resize(cropped, (dst_w, dst_h), interpolation=cv2.INTER_CUBIC)
        arch_band_y = (0, dst_h)
    else:
        # Landscape architectural / apparatus photo: preserve >= 86% of horizontal span so full portico/dome/arches remain intact!
        keep_w = max(1, int(round(ww * 0.90)))
        x0 = (ww - keep_w) // 2
        core = work[:, x0 : x0 + keep_w]
        scaled_h = min(int(round(dst_h * 0.62)), max(int(round(dst_h * 0.44)), int(round(dst_w * (wh / float(keep_w))))))
        core_resized = cv2.resize(core, (dst_w, scaled_h), interpolation=cv2.INTER_CUBIC)

        top_pad = int(round((dst_h - scaled_h) * 0.52))
        bot_pad = dst_h - scaled_h - top_pad

        # Smooth atmospheric sky gradient extension above & blurred ground perspective extension below
        top_strip = cv2.resize(core_resized[: max(8, scaled_h // 10), :], (dst_w, max(1, top_pad)), interpolation=cv2.INTER_LINEAR)
        top_strip = cv2.GaussianBlur(top_strip, (81, 81), 0)
        sky_med = np.median(core_resized[: max(6, scaled_h // 14), :], axis=(0, 1)).astype(np.float32)
        zenith_tint = np.clip(sky_med * np.array([1.06, 1.01, 0.94], dtype=np.float32), 145.0, 246.0)
        grad_t = np.linspace(0.75, 0.0, max(1, top_pad), dtype=np.float32)[:, None, None]
        top_ext = np.clip(top_strip.astype(np.float32) * (1.0 - grad_t) + zenith_tint[None, None, :] * grad_t, 0, 255).astype(np.uint8)

        bot_src = cv2.flip(core_resized[scaled_h - max(12, scaled_h // 7) :, :], 0)
        bot_strip = cv2.resize(bot_src, (dst_w, max(1, bot_pad)), interpolation=cv2.INTER_LINEAR)
        bot_strip = cv2.GaussianBlur(bot_strip, (75, 75), 0)
        ground_med = np.median(core_resized[scaled_h - max(8, scaled_h // 12) :, :], axis=(0, 1)).astype(np.float32)
        grad_b = np.linspace(0.0, 0.55, max(1, bot_pad), dtype=np.float32)[:, None, None]
        bot_ext = np.clip(bot_strip.astype(np.float32) * (1.0 - grad_b) + ground_med[None, None, :] * grad_b, 0, 255).astype(np.uint8)

        canvas = np.vstack([top_ext, core_resized, bot_ext])
        # Feather the seam bands gently so Flow sees continuous vertical space
        for seam_y in (top_pad, top_pad + scaled_h):
            sy0, sy1 = max(0, seam_y - 22), min(dst_h, seam_y + 22)
            if sy1 - sy0 >= 8:
                blurred_seam = cv2.GaussianBlur(canvas[sy0:sy1, :], (31, 31), 0)
                alpha_s = (1.0 - np.abs(np.linspace(-1.0, 1.0, sy1 - sy0, dtype=np.float32)))[:, None, None] * 0.75
                canvas[sy0:sy1, :] = np.clip(
                    canvas[sy0:sy1, :].astype(np.float32) * (1.0 - alpha_s) + blurred_seam.astype(np.float32) * alpha_s,
                    0,
                    255,
                ).astype(np.uint8)
        arch_band_y = (top_pad, top_pad + scaled_h)

    gp.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(gp), canvas)
    guide_dh_hex, guide_dh_int = _bgr_dhash64(canvas)
    raw_dh_hex, raw_dh_int = _bgr_dhash64(bgr)
    edge_vec = compute_coarse_structural_edge_vector(canvas)
    guide_sha6 = hashlib.sha1(gp.read_bytes()).hexdigest()[:6]

    return {
        "guide_path": str(gp),
        "guide_sha256": hashlib.sha256(gp.read_bytes()).hexdigest(),
        "guide_upload_sha6": guide_sha6,
        "guide_dhash64_int": guide_dh_int,
        "guide_dhash64_hex": guide_dh_hex,
        "raw_dhash64_int": raw_dh_int,
        "raw_dhash64_hex": raw_dh_hex,
        "arch_band_y": [int(arch_band_y[0]), int(arch_band_y[1])],
        "coarse_edge_vec": edge_vec,
        "faces_masked": len(faces),
        "shape": [dst_w, dst_h],
    }


def evaluate_rq_real_alignment(
    guide_meta: dict[str, Any],
    rendered_png_path: str | Path,
    *,
    min_dhash_distance: int = REAL_WORLD_REFS_MIN_DHASH_DISTANCE,
    min_edge_alignment: float = REAL_WORLD_REFS_MIN_EDGE_ALIGNMENT,
) -> dict[str, Any]:
    """
    Verifies `RQ-Real` on a Flow-rendered 3D miniature keyframe:
      1. Non-infringement: 64-bit `dHash` Hamming distance vs quarantined raw Wikimedia photo `>= 14`.
      2. Recognizable architectural/structural alignment: `27x48` coarse Sobel gradient cosine similarity `>= 0.30`.
    """
    rp = Path(rendered_png_path)
    bgr = cv2.imread(str(rp), cv2.IMREAD_COLOR)
    if bgr is None or bgr.size == 0:
        return {
            "rq_real_passed": False,
            "reason": f"missing_or_unreadable:{rp}",
            "raw_dhash_distance": 0,
            "edge_alignment_score": 0.0,
        }

    rend_hex, _ = _bgr_dhash64(bgr)
    raw_hex = str(guide_meta.get("raw_dhash64_hex") or "0" * 16)
    guide_hex = str(guide_meta.get("guide_dhash64_hex") or raw_hex)
    raw_dist = _hamming_hex(rend_hex, raw_hex)
    guide_dist = _hamming_hex(rend_hex, guide_hex)

    ref_vec = np.asarray(guide_meta.get("coarse_edge_vec") or [], dtype=np.float64)
    rend_vec = np.asarray(compute_coarse_structural_edge_vector(bgr), dtype=np.float64)
    if ref_vec.size == rend_vec.size and ref_vec.size > 0:
        denom = float(np.linalg.norm(ref_vec) * np.linalg.norm(rend_vec))
        cos_sim = float(np.dot(ref_vec, rend_vec) / denom) if denom > 1e-8 else 0.0
    else:
        cos_sim = 0.0

    dhash_ok = int(raw_dist) >= int(min_dhash_distance)
    edge_ok = float(cos_sim) >= float(min_edge_alignment)
    return {
        "rq_real_passed": bool(dhash_ok and edge_ok),
        "dhash_non_infringement_ok": bool(dhash_ok),
        "structural_alignment_ok": bool(edge_ok),
        "rendered_dhash64_hex": rend_hex,
        "raw_dhash_distance": int(raw_dist),
        "guide_dhash_distance": int(guide_dist),
        "edge_alignment_score": round(float(cos_sim), 4),
        "min_dhash_required": int(min_dhash_distance),
        "min_edge_alignment_required": float(min_edge_alignment),
    }


def verify_zero_raw_leak_in_workspace(
    project_dir: str | Path,
    raw_sha256_list: list[str],
    raw_dhash_hex_list: list[str],
    min_dhash_distance: int = REAL_WORLD_REFS_MIN_DHASH_DISTANCE,
) -> dict[str, Any]:
    """
    Audits `project_dir` to guarantee ZERO raw Wikimedia photo files (by SHA-256 or near-duplicate dHash)
    and ZERO `/tmp/aab_real_refs` paths exist inside persisted workspace JSON/PNG artifacts.
    """
    p_dir = Path(project_dir)
    raw_sha_set = {str(s).lower().strip() for s in raw_sha256_list if str(s).strip()}
    raw_hex_clean = [str(h).lower().strip() for h in raw_dhash_hex_list if str(h).strip()]
    violations: list[str] = []
    min_seen_dist = 64

    if p_dir.exists():
        for img_p in p_dir.rglob("*"):
            if not img_p.is_file():
                continue
            suf = img_p.suffix.lower()
            if suf in (".png", ".jpg", ".jpeg", ".webp"):
                f_sha = hashlib.sha256(img_p.read_bytes()).hexdigest().lower()
                if f_sha in raw_sha_set:
                    violations.append(f"exact_raw_sha256_leak:{img_p.name}")
                bgr = cv2.imread(str(img_p), cv2.IMREAD_COLOR)
                if bgr is not None and raw_hex_clean:
                    dh_hex, _ = _bgr_dhash64(bgr)
                    d_min = min(_hamming_hex(dh_hex, rh) for rh in raw_hex_clean)
                    min_seen_dist = min(min_seen_dist, d_min)
                    if d_min < min_dhash_distance:
                        violations.append(f"dhash_too_close:{img_p.name}(dist={d_min}<{min_dhash_distance})")

    return {
        "zero_raw_leak_verified": len(violations) == 0,
        "min_workspace_dhash_distance": int(min_seen_dist),
        "violations": violations,
    }


def build_r72_drone_cutaway_prompts(
    landmark_spec: dict[str, Any],
    interior_lab_desc: str,
    interior_apparatus_traits: str = "",
) -> dict[str, str]:
    """
    Constructs the 3-keyframe `K0 (30m Aerial) -> K1 (4m Real Facade) -> K2 (3D Sliced Facade Cutaway Lab)`
    prompt suite for `Rule R72 + R72-R`.
    """
    label = str(landmark_spec.get("label") or "Historic University Landmark").strip()
    arch_traits = str(landmark_spec.get("architectural_traits") or "classical brick-and-limestone university hall").strip()
    facade_traits = str(
        landmark_spec.get("facade_close_traits")
        or "textured masonry facade, classical columns, and tall multi-pane casement windows"
    ).strip()
    apparatus_clause = (
        f" featuring {interior_apparatus_traits.strip()}"
        if interior_apparatus_traits.strip()
        else ""
    )

    from pipeline.depiction_rules import FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD

    k0_prompt = (
        f"High-altitude 30-meter aerial bird's-eye establishing view angled 40 degrees downward over a stylized 3D "
        f"miniature diorama of {label}: {arch_traits}. Foreground lush tree canopies and campus walkways frame tiny "
        f"distant clothed matte-white vinyl student figures strolling the sunlit courtyard below, crisp morning golden-hour "
        f"sunlight casting long architectural shadows, deep f/8 focus from foreground treetops to horizon sky, "
        f"strictly zero text, zero signs, zero watermarks. {FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD}"
    )
    k1_prompt = (
        f"Low-altitude 4-meter gliding close approach hovering directly in front of the exact same 3D miniature "
        f"{label} building from the first reference image: {facade_traits}, crisp morning sunlight raking across tactile "
        f"3D stone and brick mortar, foreground tree branch and stone column edge framing the tall central upper-floor "
        f"research window straight ahead, strictly zero text, zero lettering, zero watermarks. {FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD}"
    )
    k2_prompt = (
        f"Architectural 3D cross-section cutaway diorama of the exact same {label} facade from the first reference image: "
        f"a clean geometric architectural slice of the front brick-and-stone wall and tall windows opens neatly away "
        f"to reveal {interior_lab_desc.strip()}{apparatus_clause} inside the building, warm tungsten laboratory key light "
        f"glowing inside against crisp sunlit campus exterior masonry outside, clothed earless noseless matte cream-white "
        f"2.5D vinyl researcher figure with bold charcoal-black 2D cartoon ink eyes and eyebrows working at the apparatus, "
        f"strictly zero text, zero labels, zero watermarks."
    )
    return {"K0": k0_prompt, "K1": k1_prompt, "K2": k2_prompt}


def prepare_episode_real_world_guides(
    project_dir: str | Path,
    visual_plan: dict[str, Any],
    dossier_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Downloads Wikimedia Commons references for all episode real-world targets into
    `/tmp/aab_real_refs/<project_id>/raw/`, builds sanitized `9:16` structural guides in
    `/tmp/aab_real_refs/<project_id>/guides/guide_<target_id>_9x16.png`, and writes non-pixel
    metadata + hashes to `03_visuals/real_world_refs_manifest.json`.
    """
    p_dir = Path(project_dir) if Path(project_dir).is_dir() else (Path(PROJECTS_DIR) / str(project_dir))
    vis_dir = p_dir / "03_visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)
    q_dir = ensure_quarantine_dir(p_dir.name)

    targets = extract_episode_real_world_targets(dossier=dossier_dir, visual_plan=visual_plan)
    entries: dict[str, dict[str, Any]] = {}
    raw_shas: list[str] = []
    raw_dhashes: list[str] = []
    upload_sha6s: list[str] = []

    for t_spec in targets:
        tid = str(t_spec["target_id"])
        fetched = fetch_wikimedia_commons_reference(
            queries=list(t_spec.get("queries") or [t_spec.get("label") or tid]),
            quarantine_dir=q_dir,
            target_id=tid,
        )
        guide_out = q_dir / "guides" / f"guide_{tid}_9x16.png"
        guide_meta = build_sanitized_9x16_structural_guide(fetched["raw_path"], guide_out)
        raw_shas.append(str(fetched["raw_sha256"]))
        raw_dhashes.append(str(fetched["raw_dhash64_hex"]))
        upload_sha6s.append(str(guide_meta["guide_upload_sha6"]))
        entries[tid] = {
            "target_id": tid,
            "category": str(t_spec.get("category") or "institution"),
            "label": str(t_spec.get("label") or tid),
            "architectural_traits": str(t_spec.get("architectural_traits") or ""),
            "facade_close_traits": str(t_spec.get("facade_close_traits") or ""),
            "commons_title": fetched["commons_title"],
            "commons_page_url": fetched["commons_page_url"],
            "source_url": fetched["commons_page_url"],
            "license": fetched["license"],
            "artist": fetched["artist"],
            "query_used": fetched["query_used"],
            "raw_sha256": fetched["raw_sha256"],
            "raw_dhash64_hex": fetched["raw_dhash64_hex"],
            "guide_dhash64_hex": guide_meta["guide_dhash64_hex"],
            "guide_upload_sha6": guide_meta["guide_upload_sha6"],
            "coarse_edge_vec": guide_meta["coarse_edge_vec"],
            "faces_masked": guide_meta["faces_masked"],
        }

    manifest = {
        "schema": "real_world_refs_manifest_v1",
        "rule": "R72-R",
        "project_id": p_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quarantine_purged": False,
        "target_count": len(entries),
        "categories_covered": sorted({e["category"] for e in entries.values()}),
        "raw_sha256_list": raw_shas,
        "raw_dhash64_list": raw_dhashes,
        "guide_upload_sha6_list": upload_sha6s,
        "targets": entries,
        "rendered_validations": {},
    }
    (vis_dir / REAL_WORLD_REFS_MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def resolve_quarantined_real_guide_path(project_id: str, target_id: str | None) -> Path | None:
    """
    Resolves `/tmp/aab_real_refs/<project_id>/guides/guide_<target_id>_9x16.png` if present during active
    `porcelain-refs` synthesis (never persisted inside workspace JSON).
    """
    if not target_id:
        return None
    spec = resolve_real_world_target_spec(str(target_id))
    resolved_tid = str(spec.get("target_id") or _safe_slug(str(target_id)))
    q_dir = (Path(REAL_WORLD_REFS_QUARANTINE_ROOT) / _safe_slug(project_id)).resolve()
    for tid_cand in (resolved_tid, _safe_slug(str(target_id))):
        gp = q_dir / "guides" / f"guide_{tid_cand}_9x16.png"
        if gp.is_file():
            return gp
    return None


def finalize_real_world_manifest_and_purge(
    project_dir: str | Path,
    visual_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Evaluates `RQ-Real` (`dHash >= 14` + coarse edge alignment `>= 0.30`) across all real-world-conditioned
    reference PNGs in `03_visuals/reference_images/`, verifies zero raw pixel leaks inside `project_dir`,
    purges `/tmp/aab_real_refs/<project_id>/`, and writes the finalized `real_world_refs_manifest.json`.
    """
    p_dir = Path(project_dir) if Path(project_dir).is_dir() else (Path(PROJECTS_DIR) / str(project_dir))
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    mf_path = vis_dir / REAL_WORLD_REFS_MANIFEST_FILENAME
    if not mf_path.exists():
        purge_res = purge_real_world_quarantine(p_dir.name)
        return {"ok": True, "skipped": True, "purge": purge_res}

    manifest = json.loads(mf_path.read_text(encoding="utf-8"))
    targets = manifest.get("targets") or {}
    plan = visual_plan if isinstance(visual_plan, dict) else {}
    rendered_checks: dict[str, Any] = {}

    for anc in plan.get("reference_anchors") or []:
        if not isinstance(anc, dict) or not anc.get("real_world_target_id"):
            continue
        raw_tid = str(anc["real_world_target_id"])
        resolved_tid = str(resolve_real_world_target_spec(raw_tid).get("target_id") or raw_tid)
        t_meta = targets.get(resolved_tid) or targets.get(raw_tid)
        if not t_meta:
            continue
        fname = str(anc.get("filename") or f"{anc.get('ref_id')}.png").strip()
        r_path = ref_dir / Path(fname).name
        if r_path.exists():
            # K2 cutaway intentionally slices open half the wall, so relax coarse exterior edge threshold slightly to 0.24 while keeping strict dHash >= 14
            min_edge = (
                0.24
                if str(anc.get("r72_relay_stage") or "") == "K2"
                else REAL_WORLD_REFS_MIN_EDGE_ALIGNMENT
            )
            rendered_checks[Path(fname).name] = evaluate_rq_real_alignment(
                t_meta,
                r_path,
                min_dhash_distance=REAL_WORLD_REFS_MIN_DHASH_DISTANCE,
                min_edge_alignment=min_edge,
            )

    sha6_set = set(manifest.get("guide_upload_sha6_list") or [])
    purge_res = purge_real_world_quarantine(p_dir.name, staged_guide_sha6_set=sha6_set)
    leak_audit = verify_zero_raw_leak_in_workspace(
        p_dir,
        raw_sha256_list=list(manifest.get("raw_sha256_list") or []),
        raw_dhash_hex_list=list(manifest.get("raw_dhash64_list") or []),
    )

    manifest["rendered_validations"] = rendered_checks
    manifest["zero_raw_leak_audit"] = leak_audit
    manifest["quarantine_purged"] = bool(purge_res.get("purged"))
    manifest["all_rq_real_passed"] = bool(
        leak_audit.get("zero_raw_leak_verified")
        and purge_res.get("purged")
        and all(bool(v.get("rq_real_passed")) for v in rendered_checks.values())
    )
    # Strip bulky transient sha6 upload tokens once purged
    manifest.pop("guide_upload_sha6_list", None)
    for t_entry in targets.values():
        if isinstance(t_entry, dict):
            t_entry.pop("guide_upload_sha6", None)

    mf_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


async def generate_landmark_drone_cutaway_demo_async(
    institution_key: str,
    out_dir: str | Path,
    *,
    interior_lab_desc: str = "a warm sunlit neuroscience laboratory with experimental instruments on an oak bench",
    apparatus_key: str | None = None,
    flow_room_id: str = "r72_landmark_drone_demo",
    cdp_port: int = DEFAULT_CDP_PORT,
) -> dict[str, Any]:
    """
    Standalone live generator for `K0 (30m Aerial) -> K1 (4m Real Facade) -> K2 (3D Sliced Facade Cutaway)`
    conditioned on real Wikimedia Commons architecture + apparatus guides in Google Flow `0-credit Image` (`x1` first-pass / `x2` retry),
    used both for Checkpoint A visual proof (`UCL` + `Harvard`) and standalone landmark verification.
    """
    from pipeline.cdp_tab_lease import enable_background_focus_emulation, release_and_close_leased_tab
    from pipeline.flow_ingredients import generate_flow_image_batch
    from pipeline.flow_live_single_worker import allocate_dedicated_flow_project_tab
    from pipeline.flow_workspace import format_flow_room_name, rename_active_flow_project
    from pipeline.studio.whale_session import DirectCDPClient

    dest_dir = Path(out_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    q_id = f"demo_{_safe_slug(institution_key)}"
    q_dir = ensure_quarantine_dir(q_id)
    inst_spec = resolve_real_world_target_spec(institution_key, fallback_category="institution")
    tid = str(inst_spec["target_id"])
    staged_sha6: set[str] = set()

    try:
        fetched = fetch_wikimedia_commons_reference(inst_spec["queries"], q_dir, target_id=tid)
        guide_p = q_dir / "guides" / f"guide_{tid}_9x16.png"
        guide_meta = build_sanitized_9x16_structural_guide(fetched["raw_path"], guide_p)
        staged_sha6.add(str(guide_meta["guide_upload_sha6"]))
        raw_dhashes = [int(fetched["raw_dhash64_int"])]

        app_guide_p: Path | None = None
        app_traits = ""
        if apparatus_key:
            app_spec = resolve_real_world_target_spec(apparatus_key, fallback_category="scientific_apparatus")
            app_traits = str(app_spec.get("architectural_traits") or "")
            app_fetched = fetch_wikimedia_commons_reference(app_spec["queries"], q_dir, target_id=str(app_spec["target_id"]))
            app_guide_p = q_dir / "guides" / f"guide_{app_spec['target_id']}_9x16.png"
            app_gmeta = build_sanitized_9x16_structural_guide(app_fetched["raw_path"], app_guide_p)
            staged_sha6.add(str(app_gmeta["guide_upload_sha6"]))
            raw_dhashes.append(int(app_fetched["raw_dhash64_int"]))

        prompts = build_r72_drone_cutaway_prompts(inst_spec, interior_lab_desc, app_traits)
        species_sheet = (
            Path(WORKSPACE_ROOT)
            / "BCI_Shorts_Channel"
            / "reference_style_anchors"
            / "expressive_25d_v8_refs"
            / "species_opt1_sheet.png"
        )

        lead_arch = (
            "Vertical 9:16 full-bleed stylized 3D cinematic miniature diorama photograph. "
            "Match the real-world architectural silhouette, roof/dome profile, column/window rhythm, and brick/stone "
            "palette of the reference guide while rendering every surface from scratch in tactile miniature 3D materials. "
        )

        k0_out = dest_dir / f"{tid}_K0_aerial_9x16.png"
        k1_out = dest_dir / f"{tid}_K1_facade_9x16.png"
        k2_out = dest_dir / f"{tid}_K2_cutaway_9x16.png"

        flow_alloc = await allocate_dedicated_flow_project_tab(cdp_port=cdp_port, project_id=flow_room_id)
        ws_url = str(flow_alloc["ws_url"])
        opened_tab_id = str(flow_alloc["tab_id"])
        opened_lease_owner = flow_alloc.get("lease_owner_id")
        uploaded_cache: set[str] = set()
        seen_srcs: set[str] = set()

        try:
            async with DirectCDPClient(ws_url) as client:
                await enable_background_focus_emulation(client)
                await client.send("Page.enable")
                await rename_active_flow_project(client, format_flow_room_name(flow_room_id, role="episode"))

                res_k0 = await generate_flow_image_batch(
                    client,
                    prompt=f"{lead_arch}{prompts['K0']}",
                    out_path=k0_out,
                    conditioning_paths=[guide_p],
                    source_dhashes=raw_dhashes,
                    uploaded_cache=uploaded_cache,
                    seen_img_srcs=seen_srcs,
                )
                if not res_k0.get("ok"):
                    raise RuntimeError(f"K0 Flow synthesis failed for {tid}: {res_k0}")

                res_k1 = await generate_flow_image_batch(
                    client,
                    prompt=f"{lead_arch}{prompts['K1']}",
                    out_path=k1_out,
                    conditioning_paths=[k0_out, guide_p],
                    source_dhashes=raw_dhashes,
                    uploaded_cache=uploaded_cache,
                    seen_img_srcs=seen_srcs,
                )
                if not res_k1.get("ok"):
                    raise RuntimeError(f"K1 Flow synthesis failed for {tid}: {res_k1}")

                k2_conds = [k1_out]
                if app_guide_p and app_guide_p.exists():
                    k2_conds.append(app_guide_p)
                elif species_sheet.exists():
                    k2_conds.append(species_sheet)
                res_k2 = await generate_flow_image_batch(
                    client,
                    prompt=(
                        "Vertical 9:16 full-bleed stylized 3D architectural cutaway miniature diorama photograph. "
                        "Preserve the exact exterior building architecture from the first reference image while slicing open "
                        f"the central front facade wall to reveal the interior room. {prompts['K2']}"
                    ),
                    out_path=k2_out,
                    conditioning_paths=k2_conds[:2],
                    source_dhashes=raw_dhashes,
                    uploaded_cache=uploaded_cache,
                    seen_img_srcs=seen_srcs,
                )
                if not res_k2.get("ok"):
                    raise RuntimeError(f"K2 Flow synthesis failed for {tid}: {res_k2}")
        finally:
            release_and_close_leased_tab(opened_tab_id, owner_id=opened_lease_owner, cdp_port=cdp_port)

        rq_k0 = evaluate_rq_real_alignment(guide_meta, k0_out)
        rq_k1 = evaluate_rq_real_alignment(guide_meta, k1_out)
        rq_k2 = evaluate_rq_real_alignment(guide_meta, k2_out, min_edge_alignment=0.22)
        return {
            "ok": True,
            "target_id": tid,
            "label": inst_spec["label"],
            "commons_title": fetched["commons_title"],
            "commons_license": fetched["license"],
            "K0": str(k0_out),
            "K1": str(k1_out),
            "K2": str(k2_out),
            "rq_real": {"K0": rq_k0, "K1": rq_k1, "K2": rq_k2},
        }
    finally:
        purge_real_world_quarantine(q_id, staged_guide_sha6_set=staged_sha6)


def render_mni152_guide_silhouette(
    brain_region: str,
    project_id: str,
    *,
    viewpoint: str | None = None,
    quarantine_root: Path | None = None,
    target_wh: tuple[int, int] = (1080, 1920),
) -> dict[str, Any]:
    """
    R85 Q1-(B) Off-Screen Structural Guide Only:
    Projects the real MNI152 3D mesh (`neuro_atlas_mni152.npz`) at the anatomically locked R85 viewpoint
    (`inferior_lateral_cutaway` for hippocampus, `midsagittal_cutaway` for thalamus/brainstem/csf,
    `lateral_opercular_retracted` for insula, `anterior_three_quarter_lateral` for prefrontal cortex)
    into `/tmp/aab_real_refs/<project_id>/guides/mni152_guide_<region>.png`.
    NEVER writes inside `WORKSPACE_ROOT` and MUST NEVER be composited directly onto final MP4 frames.
    """
    from pipeline.brain_simulator_blender import ATLAS_MANIFEST_PATH, ATLAS_NPZ_PATH, normalize_atlas_region_key

    q_dir = ensure_quarantine_dir(project_id, quarantine_root=quarantine_root)
    manifest = json.loads(Path(ATLAS_MANIFEST_PATH).read_text(encoding="utf-8"))
    reg_key = normalize_atlas_region_key(brain_region, manifest)
    reg_slug = _safe_slug(reg_key)
    out_png = (q_dir / "guides" / f"mni152_guide_{reg_slug}.png").resolve()
    ws_resolved = Path(WORKSPACE_ROOT).resolve()
    if out_png == ws_resolved or out_png.is_relative_to(ws_resolved):
        raise ValueError(f"[R85] MNI152 structural guide refused inside WORKSPACE_ROOT: {out_png}")

    rl = reg_key.lower()
    if viewpoint:
        vp_mode = str(viewpoint).strip().lower()
    elif "hippocamp" in rl:
        vp_mode = "inferior_lateral_cutaway"
    elif any(k in rl for k in ("thalam", "brainstem", "csf", "locus")):
        vp_mode = "midsagittal_cutaway"
    elif "insul" in rl:
        vp_mode = "lateral_opercular_retracted"
    else:
        vp_mode = "anterior_three_quarter_lateral"

    w, h = int(target_wh[0]), int(target_wh[1])
    canvas = np.full((h, w, 3), (18, 24, 36), dtype=np.uint8)
    npz = np.load(str(ATLAS_NPZ_PATH))

    def _project_xyz(verts: np.ndarray) -> np.ndarray:
        # MNI152: X=left(-)/right(+), Y=post(-)/ant(+), Z=inf(-)/sup(+)
        x, y, z = verts[:, 0], verts[:, 1], verts[:, 2]
        if "coronal" in vp_mode:
            u, v = x, z
        elif "midsagittal" in vp_mode:
            u, v = -y, z
        elif "inferior_lateral" in vp_mode:
            ang_z, pitch = np.deg2rad(-28.0), np.deg2rad(-16.0)
            u = -y * np.cos(ang_z) + x * np.sin(ang_z)
            v = z * np.cos(pitch) - (x * np.cos(ang_z) + y * np.sin(ang_z)) * np.sin(pitch)
        elif "opercular" in vp_mode or "lateral" in vp_mode and "three_quarter" not in vp_mode:
            u, v = -y, z
        else:  # anterior_three_quarter_lateral
            ang = np.deg2rad(38.0)
            u = x * np.cos(ang) - y * np.sin(ang)
            v = z
        scale_px = min(w, h) * 0.0044
        px = (w * 0.50 + u * scale_px).astype(np.int32)
        py = (h * 0.48 - v * scale_px).astype(np.int32)
        return np.column_stack([px, py])

    for r_name in manifest.get("regions", {}):
        vk = f"{r_name}__verts"
        fk = f"{r_name}__faces"
        if vk not in npz or fk not in npz:
            continue
        verts = np.asarray(npz[vk], dtype=np.float32)
        if "midsagittal" in vp_mode:
            verts = verts[verts[:, 0] <= 4.0] if np.any(verts[:, 0] <= 4.0) else verts
        pts2d = _project_xyz(verts)
        if pts2d.shape[0] < 8:
            continue
        hull = cv2.convexHull(pts2d)
        is_target = r_name == reg_key
        if not is_target:
            cv2.fillConvexPoly(canvas, hull, (84, 94, 106), lineType=cv2.LINE_AA)
            cv2.polylines(canvas, [hull], True, (132, 144, 158), 2, lineType=cv2.LINE_AA)

    t_vk, t_fk = f"{reg_key}__verts", f"{reg_key}__faces"
    if t_vk in npz:
        t_pts = _project_xyz(np.asarray(npz[t_vk], dtype=np.float32))
        if t_pts.shape[0] >= 4:
            t_hull = cv2.convexHull(t_pts)
            cv2.fillConvexPoly(canvas, t_hull, (255, 216, 39), lineType=cv2.LINE_AA)
            cv2.polylines(canvas, [t_hull], True, (255, 245, 190), 4, lineType=cv2.LINE_AA)

    cv2.imwrite(str(out_png), canvas)
    dh_hex, _ = _bgr_dhash64(canvas)
    return {
        "ok": True,
        "guide_path": str(out_png),
        "brain_region": reg_key,
        "viewpoint": vp_mode,
        "guide_sha256": hashlib.sha256(out_png.read_bytes()).hexdigest(),
        "guide_dhash64_hex": dh_hex,
        "screen_exposure_forbidden": True,
    }


_BANNED_LICENSE_RE = re.compile(
    r"(?:"
    r"(?:^|[^a-z0-9])nc(?:$|[^a-z0-9])"
    r"|by[-_\s/]*nc"
    r"|non[-_\s]*commercial"
    r"|(?:^|[^a-z0-9])nd(?:$|[^a-z0-9])"
    r"|by[-_\s/]*nd"
    r"|no[-_\s]*derivs?"
    r"|no[-_\s]*derivatives?"
    r"|all[-_\s]+rights[-_\s]+reserved"
    r"|fair[-_\s]+use"
    r"|\bcopyrighted\b"
    r"|\bproprietary\b"
    r"|editorial[-_\s]*only"
    r"|\bgetty\b"
    r"|\bshutterstock\b"
    r"|\balamy\b"
    r")"
)
_SHAREALIKE_LICENSE_RE = re.compile(
    r"(?:"
    r"by[-_\s/]*sa"
    r"|share[-_\s]*alike"
    r"|(?:^|[^a-z0-9])sa(?:$|[^a-z0-9])"
    r"|\bgfdl\b"
    r"|gnu\s+free\s+documentation"
    r"|wikimedia[-_\s]*open"
    r"|open[-_\s]*license"
    r")"
)
_PD_CC0_LICENSE_RE = re.compile(
    r"(?:"
    r"\bpublic[-_\s]*domain\b"
    r"|\bcc[-_\s]*0\b"
    r"|creative\s+commons\s+zero"
    r"|\bpdm\b"
    r"|(?:^|[^a-z0-9])pd(?:[-_]|$)"
    r"|\bus[-_\s]*gov\b"
    r"|\bnih\b"
    r"|\bnimh\b"
    r"|\bcdc\b"
    r"|\bnasa\b"
    r"|pre[-_\s]*1931"
    r")"
)
_CC_BY_LICENSE_RE = re.compile(
    r"(?:"
    r"(?:^|[^a-z0-9])cc[-_\s]+by(?:\s*[-_/]?\s*(?:1\.0|2\.0|2\.5|3\.0|4\.0))?(?:$|[^a-z0-9])"
    r"|creative\s+commons\s+attribution"
    r"|creativecommons\.org/licenses/by(?:/|$)"
    r")"
)


def classify_media_license(
    raw_license: str,
) -> Literal["direct_insert_pd_cc0", "direct_insert_cc_by", "flow_guide_only_cc_by_sa", "banned"]:
    """
    Classifies a media license string into strict R72-R / R88-A usage tiers:
      - `"banned"`: empty/blank, NC/ND restrictions, All Rights Reserved, Fair Use, commercial stock agencies.
      - `"flow_guide_only_cc_by_sa"`: ShareAlike/GFDL/open_license — allowed ONLY for off-screen Flow structural guides (`R72-R`), NEVER direct `R88-A` archival insert.
      - `"direct_insert_pd_cc0"`: Public Domain / CC0 / US Gov / pre-1931.
      - `"direct_insert_cc_by"`: Pure Creative Commons Attribution (zero NC/ND/SA).
    """
    norm = re.sub(r"\s+", " ", str(raw_license or "").strip().lower())
    if not norm:
        return "banned"
    if _BANNED_LICENSE_RE.search(norm):
        return "banned"
    if _SHAREALIKE_LICENSE_RE.search(norm):
        return "flow_guide_only_cc_by_sa"
    if _PD_CC0_LICENSE_RE.search(norm):
        return "direct_insert_pd_cc0"
    if _CC_BY_LICENSE_RE.search(norm):
        return "direct_insert_cc_by"
    return "banned"


def validate_real_world_refs_manifest(project_dir: str | Path) -> dict[str, Any]:
    """
    R85 Audit Gate on `03_visuals/real_world_refs_manifest.json`:
      - Fails on any Commons title matching `_SKIP_COMMONS_TITLE_TOKENS` / `_BANNED_COMMONS_CONTENT_RE`
        (FEMA, hurricane, Waarschuwing, Nateglinide bottle, alphabet blocks, digifoto postcard, Anno Domini, etc.)
        OR flagged `HARD_REJECT` in `.agents/research/r85_verified_data_and_reference_audit.json`.
      - Requires explicit `@Research` visual approval (`research_visual_approved == True`) when present/enforced.
    """
    p_dir = Path(project_dir)
    mf_path = p_dir / "03_visuals" / REAL_WORLD_REFS_MANIFEST_FILENAME
    if not mf_path.is_file():
        return {"present": False, "passed": True, "issues": []}
    doc = json.loads(mf_path.read_text(encoding="utf-8"))
    audit_rejects: set[str] = set()
    audit_json = Path(WORKSPACE_ROOT) / ".agents" / "research" / "r85_verified_data_and_reference_audit.json"
    if audit_json.is_file():
        try:
            adoc = json.loads(audit_json.read_text(encoding="utf-8"))
            for row in (adoc.get("part_3_real_world_refs_manifest_audit") or {}).get("per_file_audit_and_replacements") or []:
                if str(row.get("verdict") or "") == "HARD_REJECT" and row.get("current_commons_title"):
                    audit_rejects.add(str(row["current_commons_title"]).strip())
        except Exception:
            pass

    targets = doc.get("targets") or doc.get("references") or []
    if isinstance(targets, dict):
        targets = list(targets.values())
    issues: list[str] = []
    for entry in targets:
        if not isinstance(entry, dict):
            continue
        tid = str(entry.get("target_id") or "")
        ctitle = str(entry.get("commons_title") or "")
        blocked, b_reason = is_commons_candidate_blocked(ctitle)
        if blocked:
            issues.append(f"[real_world_ref_blocked] {tid}: '{ctitle}' -> {b_reason} (R85)")
        elif ctitle in audit_rejects:
            issues.append(f"[real_world_ref_hard_reject] {tid}: '{ctitle}' rejected by @Research visual audit (R85)")
        if entry.get("research_visual_approved") is False:
            issues.append(f"[real_world_ref_rejected] {tid}: research_visual_approved=False (R85)")
        lic_raw = str(
            entry.get("license")
            or entry.get("license_short_name")
            or entry.get("commons_license")
            or ""
        ).strip().lower()
        prov_src = str(entry.get("source_url") or entry.get("commons_url") or ctitle).strip()

        if "license" in entry or "license_short_name" in entry or "commons_license" in entry or doc.get("r85_mode"):
            if classify_media_license(lic_raw) == "banned":
                issues.append(
                    f"[real_world_ref_unlicensed] {tid}: missing/non-open license '{lic_raw}' (require Public Domain/CC0/CC-BY/CC-BY-SA) (R85)"
                )
        if not prov_src:
            issues.append(f"[real_world_ref_missing_provenance] {tid}: missing source_url/commons_title provenance (R85)")
    return {"present": True, "passed": len(issues) == 0, "issues": issues}


__all__ = [
    "INSTITUTION_ICONIC_LANDMARK_MAP",
    "NEUROANATOMY_CUTAWAY_MAP",
    "SCIENTIFIC_APPARATUS_QUERY_MAP",
    "URBAN_LANDMARK_QUERY_MAP",
    "build_r72_drone_cutaway_prompts",
    "build_sanitized_9x16_structural_guide",
    "classify_media_license",
    "compute_coarse_structural_edge_vector",
    "ensure_quarantine_dir",
    "evaluate_rq_real_alignment",
    "extract_episode_real_world_targets",
    "fetch_wikimedia_commons_reference",
    "finalize_real_world_manifest_and_purge",
    "generate_landmark_drone_cutaway_demo_async",
    "is_commons_candidate_blocked",
    "prepare_episode_real_world_guides",
    "purge_real_world_quarantine",
    "render_mni152_guide_silhouette",
    "resolve_quarantined_real_guide_path",
    "resolve_real_world_target_spec",
    "validate_real_world_refs_manifest",
    "verify_zero_raw_leak_in_workspace",
]

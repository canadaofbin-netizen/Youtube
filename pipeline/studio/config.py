"""
ALL ABOUT BRAIN - YouTube Studio Autonomous Operations Configuration
Defines North American 5-Slot timetable, 7-Pillar playlist mapping,
bilingual YouTube Studio Polymer UI selectors, and AI content declaration schemas.
"""

from pathlib import Path
from typing import Any

# Channel Identity
CHANNEL_NAME = "ALL ABOUT BRAIN"
CHANNEL_HANDLE = "@AllAboutBrainOfficial"
CHANNEL_ID = "UC4FeioYYv9X04Di07_MfZ7g"
STUDIO_BASE_URL = f"https://studio.youtube.com/channel/{CHANNEL_ID}"
STUDIO_CONTENT_URL = f"https://studio.youtube.com/channel/{CHANNEL_ID}/videos/short"
YOUTUBE_WATCH_BASE_URL = "https://www.youtube.com/shorts/"

# Two-Tier Channel Localization & Tax/Monetization Architecture (R36)
# 1. Channel Country of Residence: Locked to South Korea (KR) for Korean legal residency,
#    AdSense identity/PIN verification, Korean bank payouts, and US-KR W-8BEN tax treaty (10% reduced withholding).
# 2. Upload Defaults & Video/Metadata Language: Locked to English (United States) (en-US)
#    for US Shorts feed algorithm routing and Tier-1 US RPM monetization.
CHANNEL_RESIDENCE_COUNTRY = "KR"
CHANNEL_RESIDENCE_COUNTRY_NAME = "South Korea"
CHANNEL_RESIDENCE_COUNTRY_KO = "\\ub300\\ud55c\\ubbfc\\uad6d"
VIDEO_LANGUAGE_CODE = "en-US"
VIDEO_LANGUAGE_LABEL = "English (United States)"
VIDEO_LANGUAGE_LABEL_KO = "\\uc601\\uc5b4(\\ubbf8\\uad6d)"
TITLE_DESCRIPTION_LANGUAGE_CODE = "en-US"
TITLE_DESCRIPTION_LANGUAGE_LABEL = "English (United States)"
TITLE_DESCRIPTION_LANGUAGE_LABEL_KO = "\\uc601\\uc5b4(\\ubbf8\\uad6d)"
DEFAULT_VIDEO_CATEGORY = "Science & Technology"
DEFAULT_VIDEO_CATEGORY_STUDIO = "Science and technology"
DEFAULT_VIDEO_CATEGORY_KO = "\\uacfc\\ud559 \\uae30\\uc220"
TARGET_AUDIENCE_REGION = "US"

CHANNEL_LOCALIZATION_SPEC: dict[str, Any] = {
    "channel_residence_country_code": CHANNEL_RESIDENCE_COUNTRY,
    "channel_residence_country_name": CHANNEL_RESIDENCE_COUNTRY_NAME,
    "channel_residence_country_ko": CHANNEL_RESIDENCE_COUNTRY_KO,
    "tax_treaty_regime": "US-KR Tax Treaty (W-8BEN 10% reduced US source withholding; AdSense KR residency)",
    "video_language_code": VIDEO_LANGUAGE_CODE,
    "video_language_label": VIDEO_LANGUAGE_LABEL,
    "video_language_label_ko": VIDEO_LANGUAGE_LABEL_KO,
    "title_description_language_code": TITLE_DESCRIPTION_LANGUAGE_CODE,
    "title_description_language_label": TITLE_DESCRIPTION_LANGUAGE_LABEL,
    "title_description_language_label_ko": TITLE_DESCRIPTION_LANGUAGE_LABEL_KO,
    "default_category": DEFAULT_VIDEO_CATEGORY,
    "target_audience_region": TARGET_AUDIENCE_REGION,
}

# Browser & DevTools Protocol
_WIN_WHALE = Path(r"C:\Program Files\Naver\Naver Whale\Application\whale.exe")
WHALE_EXECUTABLE = _WIN_WHALE if _WIN_WHALE.exists() or Path(r"C:\Program Files").exists() else Path("/usr/bin/docker")
DEFAULT_CDP_HOST = "127.0.0.1"
DEFAULT_CDP_PORT = 9222

# Staging Buffer Path
import os as _os
_WIN_STAGING = Path(r"g:\My Drive\Kyubin_Yun_Workspace\07_Youtube\BCI_Shorts_Channel\staging_queue.json")
STAGING_QUEUE_FILE = (
    _WIN_STAGING
    if _os.name == "nt" and _WIN_STAGING.parent.exists()
    else Path(__file__).resolve().parents[2] / "BCI_Shorts_Channel" / "staging_queue.json"
)

# 5-Slot Timetable (ET / PT / KST)
SLOT_TIMETABLE: dict[int, dict[str, Any]] = {
    1: {
        "slot_id": 1,
        "name": "Morning Commute",
        "time_et": "07:30",
        "time_et_12h": "7:30 AM",
        "time_pt": "04:30",
        "time_kst": "20:30",
        "kst_day_offset": 0,
        "recommended_pillars": ["brain_health"],
        "target_cognitive_state": "Light, practical neuro-stimulation during transit; quick physical analogies.",
        "description": "07:30 AM ET (20:30 KST) - Morning Commute (brain_health)"
    },
    2: {
        "slot_id": 2,
        "name": "Midday Peak",
        "time_et": "12:00",
        "time_et_12h": "12:00 PM",
        "time_pt": "09:00",
        "time_kst": "01:00",
        "kst_day_offset": 1,
        "recommended_pillars": ["bci_tech", "brain_news"],
        "target_cognitive_state": "Global peak traffic, high tech authority & breakthrough neuro-tech news.",
        "description": "12:00 PM ET (01:00 KST +1) - Midday Peak (bci_tech / brain_news)"
    },
    3: {
        "slot_id": 3,
        "name": "Afternoon Slump",
        "time_et": "16:00",
        "time_et_12h": "4:00 PM",
        "time_pt": "13:00",
        "time_kst": "05:00",
        "kst_day_offset": 1,
        "recommended_pillars": ["brain_basics", "brain_mysteries"],
        "target_cognitive_state": "Fatigue relief, counter-intuitive paradox hooks, sensory illusions.",
        "description": "04:00 PM ET (05:00 KST +1) - Afternoon Slump (brain_basics / brain_mysteries)"
    },
    4: {
        "slot_id": 4,
        "name": "Evening Prime",
        "time_et": "20:00",
        "time_et_12h": "8:00 PM",
        "time_pt": "17:00",
        "time_kst": "09:00",
        "kst_day_offset": 1,
        "recommended_pillars": ["brain_history"],
        "target_cognitive_state": "Sofa relaxation, full SIMUL-ARC historical drama immersion.",
        "description": "08:00 PM ET (09:00 KST +1) - Evening Prime (brain_history)"
    },
    5: {
        "slot_id": 5,
        "name": "Late Night / West Coast",
        "time_et": "22:30",
        "time_et_12h": "10:30 PM",
        "time_pt": "19:30",
        "time_kst": "11:30",
        "kst_day_offset": 1,
        "recommended_pillars": ["bci_ethics", "brain_mysteries"],
        "target_cognitive_state": "Bedtime existential wonder, cognitive privacy debate, infinite loop.",
        "description": "10:30 PM ET (11:30 KST +1) - Late Night / West Coast (bci_ethics / brain_mysteries)"
    }
}

# Pillar to Default Slot Mapping
PILLAR_SLOT_MAP: dict[str, int] = {
    "brain_health": 1,
    "bci_tech": 2,
    "brain_news": 2,
    "brain_basics": 3,
    "brain_mysteries": 3,
    "brain_history": 4,
    "bci_ethics": 5,
}

# 7 Content Pillar Playlists
PILLAR_PLAYLIST_MAP: dict[str, dict[str, str]] = {
    "bci_tech": {
        "title": "BCI Tech Explained | Neural Interfaces & Mind Decoding",
        "description": "Explaining the engineering and biophysics behind Brain-Computer Interfaces, Neuralink, and neural prosthetics."
    },
    "brain_news": {
        "title": "Brain News | Breakthroughs, Clinical Trials & Neuro-Tech",
        "description": "Latest peer-reviewed breakthroughs in neurotechnology and FDA clinical trials."
    },
    "brain_history": {
        "title": "Brain History & Evolution | How Humanity Found the Mind",
        "description": "From ancient trepanation and Egyptian embalming to Phineas Gage and modern neuroscience."
    },
    "brain_basics": {
        "title": "Brain Basics & Biophysics | Action Potentials & Neural Circuits",
        "description": "The fundamental biophysics of how 86 billion neurons compute and transmit electricity."
    },
    "brain_mysteries": {
        "title": "Brain Mysteries & Paradoxes | Consciousness & Perception",
        "description": "Déjà vu, sensory binding, split-brain phenomena, and unsolved paradoxes of consciousness."
    },
    "brain_health": {
        "title": "Brain Health & Optimization | Sleep, Glymphatic Flush & Dopamine",
        "description": "Evidence-based neuroscience protocols for sleep, glymphatic fluid flushing, and cognitive longevity."
    },
    "bci_ethics": {
        "title": "BCI Ethics & Future of Mind | Cognitive Privacy & Neurorights",
        "description": "Neural cryptography, cognitive privacy, mind reading ethics, and the future of human agency."
    }
}

# YouTube Studio Polymer UI Selectors (Bilingual English & Korean Fallbacks)
STUDIO_SELECTORS: dict[str, list[str]] = {
    "create_button": [
        "#create-icon",
        "ytcp-button#create-icon",
        "button[aria-label='Create']",
        "button[aria-label='\\ub9cc\\ub4e4\\uae30']",
        "ytcp-icon-button#create-icon",
        "ytcp-button[aria-label*='Create']"
    ],
    "upload_video_item": [
        "tp-yt-paper-item#text-item-0",
        "[test-id='upload-beta']",
        "ytcp-text-menu tp-yt-paper-item:has-text('Upload videos')",
        "tp-yt-paper-item:has-text('\\ub3d9\\uc601\\uc0c1 \\uc5c5\\ub85c\\ub4dc')",
        "#text-item-0"
    ],
    "file_input": [
        "input[type='file'][name='Filedata']",
        "ytcp-upload-dialog input[type='file']",
        "#select-files-button input[type='file']",
        "input[type='file']"
    ],
    "title_input": [
        "ytcp-social-suggestions-textbox[aria-label*='title'] #textbox",
        "ytcp-social-suggestions-textbox[aria-label*='\\uc81c\\ubaa9'] #textbox",
        "#title-textarea #textbox",
        "div#textbox[aria-label*='title']",
        "div#textbox[aria-label*='\\uc81c\\ubaa9']",
        "div#textbox[contenteditable='true']"
    ],
    "description_input": [
        "div#textbox[aria-label*='Tell viewers']",
        "div#textbox[aria-label*='viewers']",
        "div#textbox[aria-label*='\\uc2dc\\uccad\\uc790\\uc5d0\\uac8c']",
        "ytcp-social-suggestions-textbox[aria-label*='description'] #textbox",
        "ytcp-social-suggestions-textbox[aria-label*='\\uc124\\uba85'] #textbox",
        "#description-textarea #textbox",
        "div#description-textarea div#textbox"
    ],
    "thumbnail_file_input": [
        "ytcp-thumbnails-compact-editor-uploader input[type='file']",
        "input#file-loader",
        "ytcp-thumbnail-editor input[type='file']",
        "input[type='file'][accept*='image']"
    ],
    "not_made_for_kids_radio": [
        "tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS']",
        "tp-yt-paper-radio-button#radio-off",
        "tp-yt-paper-radio-button[aria-label*='Not made for kids']",
        "tp-yt-paper-radio-button[aria-label*='\\uc544\\ub3d9\\uc6a9\\uc774 \\uc544\\ub2d9\\ub2c8\\ub2e4']",
        "[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"
    ],
    "show_more_button": [
        "#toggle-button",
        "ytcp-button#toggle-button",
        "button:has-text('Show more')",
        "button:has-text('\\uc790\\uc138\\ud788 \\ubcf4\\uae30')",
        "#expand-button"
    ],
    "altered_content_checkbox": [
        "tp-yt-paper-radio-button[name='VIDEO_HAS_ALTERED_CONTENT_YES']",
        "[aria-label*='Yes, AI was used']",
        "ytcp-checkbox-lit[name='is-altered-content']",
        "tp-yt-paper-checkbox[name='is-altered-content']",
        "tp-yt-paper-checkbox:has-text('Altered or synthetic content')",
        "tp-yt-paper-checkbox:has-text('\\ubcc0\\ud615 \\ub610\\ub294 \\uc0dd\\uc131\\ub41c \\ucf58\\ud150\\uce20')",
        "#checkbox[aria-label*='altered']",
        "#altered-content-checkbox",
        "tp-yt-paper-radio-button[name='ALTERED_CONTENT_YES']",
        "tp-yt-paper-radio-button[name='YES']",
        "tp-yt-paper-radio-button:has-text('Yes')",
        "tp-yt-paper-radio-button:has-text('\\uc608')",
        "ytcp-altered-content-selector tp-yt-paper-radio-button:first-child",
        "[test-id='altered-content-yes']"
    ],
    "next_button": [
        "#next-button",
        "ytcp-button#next-button",
        "button:has-text('Next')",
        "button:has-text('\\ub2e4\\uc74c')"
    ],
    "visibility_unlisted_radio": [
        "tp-yt-paper-radio-button[name='UNLISTED']",
        "tp-yt-paper-radio-button[aria-label*='Unlisted']",
        "tp-yt-paper-radio-button[aria-label*='\\uc77c\\ubd80 \\uacf5\\uac1c']",
        "#unlisted-radio-button"
    ],
    "visibility_public_radio": [
        "tp-yt-paper-radio-button[name='PUBLIC']",
        "tp-yt-paper-radio-button[aria-label*='Public']",
        "tp-yt-paper-radio-button[aria-label*='\\uacf5\\uac1c']"
    ],
    "visibility_private_radio": [
        "tp-yt-paper-radio-button[name='PRIVATE']",
        "tp-yt-paper-radio-button[aria-label*='Private']",
        "tp-yt-paper-radio-button[aria-label*='\\ube44\\uacf5\\uac1c']"
    ],
    "visibility_schedule_radio": [
        "tp-yt-paper-radio-button[name='SCHEDULE']",
        "#schedule-radio-button",
        "tp-yt-paper-radio-button[aria-label*='Schedule']",
        "tp-yt-paper-radio-button[aria-label*='\\uc608\\uc57d']"
    ],
    "schedule_datepicker": [
        "#datepicker-trigger",
        "ytcp-datetime-picker #datepicker-trigger",
        "input[aria-label*='Date']",
        "input[aria-label*='\\ub0a0\\uc9dc']"
    ],
    "schedule_timepicker": [
        "#time-of-day-trigger",
        "ytcp-datetime-picker input[aria-label*='Time']",
        "ytcp-datetime-picker input[aria-label*='\\uc2dc\\uac04']"
    ],
    "done_button": [
        "#done-button",
        "ytcp-button#done-button",
        "button:has-text('Done')",
        "button:has-text('Save')",
        "button:has-text('Schedule')",
        "button:has-text('\\uc644\\ub8cc')",
        "button:has-text('\\uc800\\uc7a5')",
        "button:has-text('\\uc608\\uc57d')"
    ],
    "dialog_close_button": [
        "#close-button",
        "ytcp-button#close-button",
        "button[aria-label='Close']",
        "button[aria-label='\\ub2eb\\uae30']"
    ],
    "video_link": [
        "a.ytcp-video-info",
        "span.ytcp-video-info a",
        "a[href*='/shorts/']",
        "a[href*='youtu.be/']"
    ],
    "video_language_dropdown": [
        "ytcp-form-language-input#audio-language #trigger",
        "#audio-language ytcp-text-dropdown-trigger#trigger",
        "ytcp-form-language-input[label*='Video language'] #trigger",
        "ytcp-form-language-input[label*='\\ub3d9\\uc601\\uc0c1 \\uc5b8\\uc5b4'] #trigger"
    ],
    "title_description_language_dropdown": [
        "ytcp-form-language-input#metadata-language #trigger",
        "#metadata-language ytcp-text-dropdown-trigger#trigger",
        "ytcp-form-language-input[label*='Title and description language'] #trigger",
        "ytcp-form-language-input[label*='\\uc81c\\ubaa9 \\ubc0f \\uc124\\uba85 \\uc5b8\\uc5b4'] #trigger"
    ],
    "language_option_en_us": [
        "tp-yt-paper-item:has-text('English (United States)')",
        "tp-yt-paper-item:has-text('\\uc601\\uc5b4(\\ubbf8\\uad6d)')"
    ]
}

# YouTube Studio Settings & Localization Selectors (Channel KR Residence + Upload Defaults en-US)
STUDIO_SETTINGS_SELECTORS: dict[str, list[str]] = {
    "settings_nav_item": [
        "tp-yt-paper-icon-item#settings-item",
        "#settings-item",
        "a#settings-item",
        "[test-id='settings-item']"
    ],
    "channel_tab": [
        "ytcp-settings-dialog li#channel",
        "li#channel",
        "tp-yt-paper-item#channel"
    ],
    "country_of_residence_trigger": [
        "ytcp-form-select#country-of-residence-select #trigger",
        "#country-of-residence-select ytcp-text-dropdown-trigger#trigger",
        "#country-of-residence-select"
    ],
    "country_option_south_korea": [
        "tp-yt-paper-item:has-text('South Korea')",
        "tp-yt-paper-item:has-text('\\ub300\\ud55c\\ubbfc\\uad6d')",
        "tp-yt-paper-item:has-text('\\ud55c\\uad6d')"
    ],
    "uploads_tab": [
        "ytcp-settings-dialog li#uploads",
        "li#uploads",
        "tp-yt-paper-item#uploads"
    ],
    "uploads_advanced_subtab": [
        "ytcp-settings-dialog tp-yt-paper-tab#advancedSettings",
        "tp-yt-paper-tab#advancedSettings",
        "tp-yt-paper-tab:has-text('Advanced settings')",
        "tp-yt-paper-tab:has-text('\\uace0\\uae09 \\uc124\\uc815')"
    ],
    "audio_language_trigger": [
        "ytcp-form-language-input#audio-language #trigger",
        "#audio-language #trigger"
    ],
    "metadata_language_trigger": [
        "ytcp-form-language-input#metadata-language #trigger",
        "#metadata-language #trigger"
    ],
    "category_trigger": [
        "ytcp-form-select#category-select #trigger",
        "#category-select #trigger"
    ],
    "settings_save_button": [
        "ytcp-settings-dialog ytcp-button#submit-button",
        "ytcp-settings-dialog #submit-button"
    ],
    "settings_cancel_button": [
        "ytcp-settings-dialog ytcp-button#cancel-button",
        "ytcp-settings-dialog #cancel-button"
    ]
}

# Community & Comments Selectors
COMMUNITY_SELECTORS: dict[str, list[str]] = {
    "comment_input_box": [
        "#simplebox-placeholder",
        "#placeholder-area",
        "div#contenteditable-root",
        "#comment-dialog #contenteditable-root"
    ],
    "comment_submit_button": [
        "#submit-button",
        "ytd-button-renderer#submit-button button",
        "button[aria-label*='Comment']",
        "button[aria-label*='\\ub313\\uae00']"
    ],
    "comment_action_menu": [
        "ytd-comment-view-model ytd-menu-renderer yt-icon-button",
        "#action-menu yt-icon-button",
        "yt-icon-button#action-menu-button",
        "#button.ytd-menu-renderer"
    ],
    "pin_menu_item": [
        "tp-yt-paper-item:has-text('Pin')",
        "tp-yt-paper-item:has-text('\\uace0\\uc815')",
        "ytd-menu-service-item-renderer:has-text('Pin')",
        "ytd-menu-service-item-renderer:has-text('\\uace0\\uc815')"
    ],
    "confirm_pin_button": [
        "yt-button-renderer#confirm-button button",
        "#confirm-button",
        "button:has-text('Pin')",
        "button:has-text('\\uace0\\uc815')"
    ]
}

# A/B Testing Studio Thumbnail Replacement Selectors
THUMBNAIL_SWAP_SELECTORS: dict[str, list[str]] = {
    "thumbnail_container": [
        "ytcp-thumbnail-editor",
        "ytcp-thumbnails-compact-editor-uploader",
        "#thumbnail-editor",
    ],
    "thumbnail_options_menu": [
        "ytcp-thumbnail-editor ytcp-button#options-button",
        "ytcp-thumbnail-editor button[aria-label='Options']",
        "ytcp-thumbnail-editor button[aria-label='\\uc635\\uc158']",
        "ytcp-button#options-button",
        "ytcp-thumbnails-compact-editor-uploader yt-icon-button#options-menu",
        "ytcp-thumbnails-compact-editor-uploader #options-menu",
        "ytcp-thumbnail-editor yt-icon-button",
    ],
    "change_thumbnail_item": [
        "tp-yt-paper-item[test-id='CHANGE']",
        "tp-yt-paper-item:has-text('Change')",
        "tp-yt-paper-item:has-text('\\ubcc0\\uacbd')",
        "tp-yt-paper-item:has-text('Upload')",
        "tp-yt-paper-item:has-text('\\uc5c5\\ub85c\\ub4dc')",
    ],
    "details_save_button": [
        "ytcp-video-metadata-editor #save button",
        "ytcp-button#save",
        "#save",
        "#save-button",
        "ytcp-button#save-button",
        "button:has-text('Save')",
        "button:has-text('\\uc800\\uc7a5')",
    ],
}

# Short-to-Short Related Video & Seed-Rescue Graph Configuration (R35-B)
_WIN_LINK_GRAPH = Path(r"g:\My Drive\Kyubin_Yun_Workspace\07_Youtube\BCI_Shorts_Channel\short_link_graph.json")
SHORT_LINK_GRAPH_FILE = (
    _WIN_LINK_GRAPH
    if _os.name == "nt" and _WIN_LINK_GRAPH.parent.exists()
    else Path(__file__).resolve().parents[2] / "BCI_Shorts_Channel" / "short_link_graph.json"
)
SEED_PROTECTION_LOCK_HOURS: float = 24.0
ANCHOR_MIN_VIEWS: int = 250
SEED_STARVED_MAX_IMPRESSIONS: int = 100
STUDIO_TAB_RECYCLE_INTERVAL: int = 3
AFFINITY_WEIGHTS: dict[str, float] = {
    "anatomy": 0.40,
    "pillar_mode": 0.25,
    "lexical": 0.20,
    "retention_seed": 0.15,
}

RELATED_VIDEO_SELECTORS: dict[str, list[str]] = {
    "trigger": [
        "#linked-video-editor-link ytcp-dropdown-trigger",
        "#linked-video-editor-link",
        "ytcp-shorts-content-links #linked-video-editor-link",
        "ytcp-video-metadata-related-video #select-button",
        "ytcp-video-metadata-related-video ytcp-dropdown-trigger",
        "ytcp-video-metadata-related-video",
    ],
    "readback_container": [
        "#linked-video-editor-link",
        "ytcp-shorts-content-links #linked-video-editor-link",
        "ytcp-video-metadata-related-video",
    ],
    "picker_dialog": [
        "ytcp-video-pick-dialog",
        "ytcp-dialog#inner-dialog",
    ],
    "search_input": [
        "ytcp-video-pick-dialog input#search-yours",
        "input#search-yours",
        "ytcp-video-pick-dialog input[placeholder*='Search your videos']",
        "ytcp-video-pick-dialog input[placeholder*='\\ub0b4 \\ub3d9\\uc601\\uc0c1 \\uac80\\uc0c9']",
    ],
    "entity_card": [
        "ytcp-video-pick-dialog ytcp-entity-card",
        "ytcp-entity-card.card",
    ],
    "save_button": [
        "ytcp-video-metadata-editor #save button",
        "ytcp-button#save",
        "#save",
        "button:has-text('Save')",
        "button:has-text('\\uc800\\uc7a5')",
    ],
}

PLAYLIST_SELECTORS: dict[str, list[str]] = {
    "trigger": [
        "ytcp-video-metadata-playlists ytcp-dropdown-trigger",
        "ytcp-video-metadata-playlists ytcp-text-dropdown-trigger",
        "ytcp-video-metadata-playlists",
    ],
    "dialog": [
        "ytcp-playlist-dialog tp-yt-paper-dialog#dialog",
        "ytcp-playlist-dialog",
    ],
    "search_input": [
        "ytcp-playlist-dialog input#search-input",
        "ytcp-playlist-dialog input[aria-label*='playlist']",
        "ytcp-playlist-dialog input[aria-label*='\\uc7ac\\uc0dd\\ubaa9\\ub85d']",
    ],
    "new_playlist_button": [
        "ytcp-playlist-dialog ytcp-button.new-playlist-button",
        "ytcp-playlist-dialog #new-playlist-button",
        "ytcp-playlist-dialog button:has-text('Create playlist')",
        "ytcp-playlist-dialog button:has-text('New playlist')",
        "ytcp-playlist-dialog button:has-text('\\uc0c8 \\uc7ac\\uc0dd\\ubaa9\\ub85d')",
    ],
    "new_playlist_menu_item": [
        "ytcp-playlist-dialog ytcp-text-menu#action-menu tp-yt-paper-item#text-item-0",
        "tp-yt-paper-item:has-text('New playlist')",
        "tp-yt-paper-item:has-text('Create playlist')",
        "tp-yt-paper-item:has-text('\\uc0c8 \\uc7ac\\uc0dd\\ubaa9\\ub85d')",
    ],
    "creation_dialog": [
        "ytcp-playlist-creation-dialog tp-yt-paper-dialog#dialog",
    ],
    "creation_title_input": [
        "ytcp-playlist-creation-dialog div#textbox[aria-label*='Add title']",
        "ytcp-playlist-creation-dialog #title-textarea #textbox",
        "ytcp-playlist-creation-dialog div#textbox[aria-label*='title']",
        "ytcp-playlist-creation-dialog div#textbox[aria-label*='Title']",
        "ytcp-playlist-creation-dialog div#textbox[aria-label*='\\uc81c\\ubaa9']",
    ],
    "creation_description_input": [
        "ytcp-playlist-creation-dialog div#textbox[aria-label*='Add description']",
        "ytcp-playlist-creation-dialog #description-textarea #textbox",
        "ytcp-playlist-creation-dialog div#textbox[aria-label*='description']",
        "ytcp-playlist-creation-dialog div#textbox[aria-label*='Description']",
        "ytcp-playlist-creation-dialog div#textbox[aria-label*='\\uc124\\uba85']",
    ],
    "creation_submit_button": [
        "ytcp-playlist-creation-dialog ytcp-button#create-button",
        "ytcp-playlist-creation-dialog #create-button",
    ],
    "done_button": [
        "ytcp-playlist-dialog ytcp-button.save-button",
        "ytcp-playlist-dialog ytcp-button.done-button",
        "ytcp-playlist-dialog #done-button",
        "ytcp-playlist-dialog button:has-text('Save')",
        "ytcp-playlist-dialog button:has-text('Done')",
        "ytcp-playlist-dialog button:has-text('\\uc800\\uc7a5')",
        "ytcp-playlist-dialog button:has-text('\\uc644\\ub8cc')",
    ],
}

# AI Content Disclosure Policy Config
AI_CONTENT_DECLARATION = {
    "is_altered_content": True,
    "sound_or_realistic_video": True,
    "label_required": True,
    "note": "AI-generated visual synthesis and neural voice (R4 compliance)"
}

# Daily Analytics & Growth Reporting Paths
_WIN_REPORTS = Path(r"g:\My Drive\Kyubin_Yun_Workspace\07_Youtube\BCI_Shorts_Channel\reports")
REPORTS_ROOT_DIR = (
    _WIN_REPORTS
    if _os.name == "nt" and _WIN_REPORTS.parent.exists()
    else Path(__file__).resolve().parents[2] / "BCI_Shorts_Channel" / "reports"
)
DAILY_REPORTS_DIR = REPORTS_ROOT_DIR / "daily"
LATEST_REPORT_FILE = REPORTS_ROOT_DIR / "LATEST_DAILY_REPORT.md"
MASTER_PROMPT_FILE = REPORTS_ROOT_DIR / "DAILY_REPORT_MASTER_PROMPT.md"

STUDIO_ANALYTICS_URLS: dict[str, str] = {
    "dashboard": f"https://studio.youtube.com/channel/{CHANNEL_ID}",
    "content_shorts": f"https://studio.youtube.com/channel/{CHANNEL_ID}/videos/short",
    "analytics_overview": f"https://studio.youtube.com/channel/{CHANNEL_ID}/analytics/tab-overview/period-default",
    "analytics_content": f"https://studio.youtube.com/channel/{CHANNEL_ID}/analytics/tab-reach_viewers/period-default",
    "analytics_audience": f"https://studio.youtube.com/channel/{CHANNEL_ID}/analytics/tab-build_audience/period-default",
    "analytics_research": f"https://studio.youtube.com/channel/{CHANNEL_ID}/analytics/tab-research/period-default",
}

STUDIO_ANALYTICS_SELECTORS: dict[str, list[str]] = {
    "metric_cards": [
        "yta-key-metric-card",
        "yta-key-metric-block",
        "ytcp-analytics-metric-card",
        "[id*='metric-card']",
    ],
    "realtime_card": [
        "yta-realtime-card",
        "yta-latest-activity-card",
        "ytcp-realtime-activity-card",
    ],
    "shorts_chip": [
        "ytcp-chip:has-text('Shorts')",
        "tp-yt-paper-tab:has-text('Shorts')",
        "button:has-text('Shorts')",
    ],
    "video_rows": [
        "ytcp-video-row",
        "#row-container",
    ],
    "table_cards": [
        "yta-table-card",
        "yta-card-container",
        "yta-PerformersCard",
    ],
}


def get_slot_info(slot_id: int) -> dict[str, Any]:
    """Retrieves slot schedule and metadata for a slot (1-5)."""
    return SLOT_TIMETABLE.get(slot_id, SLOT_TIMETABLE[2])


def get_pillar_default_slot(pillar_id: str) -> int:
    """Returns the recommended slot ID (1-5) for a given content pillar."""
    if not pillar_id:
        return 2
    raw = str(pillar_id).lower()
    if raw in PILLAR_SLOT_MAP:
        return PILLAR_SLOT_MAP[raw]
    if "health" in raw:
        return 1
    elif "tech" in raw or "news" in raw:
        return 2
    elif "basic" in raw:
        return 3
    elif "history" in raw:
        return 4
    elif "ethic" in raw:
        return 5
    elif "myster" in raw:
        return 3
    return 2



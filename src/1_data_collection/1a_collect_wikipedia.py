"""
Heritage Document Collector — Curated Global Wikipedia Scraper
Fetches Wikipedia articles by exact title for known world heritage sites.
Guarantees every document is a real, named heritage site or closely related topic.
"""

import wikipedia
import json
import os
import time
from datetime import datetime

# ── Curated list of global heritage sites and related topics ──────────────────
# Organised by region. Every entry is a real Wikipedia article title.

HERITAGE_ARTICLES = [
    # ── India: UNESCO World Heritage Sites ────────────────────────────────────
    "Ajanta Caves",
    "Ellora Caves",
    "Taj Mahal",
    "Agra Fort",
    "Fatehpur Sikri",
    "Group of Monuments at Hampi",
    "Khajuraho Group of Monuments",
    "Elephanta Caves",
    "Great Living Chola Temples",
    "Group of Monuments at Pattadakal",
    "Sundarbans National Park",
    "Nanda Devi and Valley of Flowers National Parks",
    "Buddhist Monuments at Sanchi",
    "Humayun's Tomb",
    "Qutb Minar and its Monuments",
    "Mountain Railways of India",
    "Mahabodhi Temple Complex at Bodh Gaya",
    "Rock Shelters of Bhimbetka",
    "Champaner-Pavagadh Archaeological Park",
    "Chhatrapati Shivaji Maharaj Terminus",
    "Red Fort Complex",
    "Jantar Mantar, Jaipur",
    "Western Ghats",
    "Hill Forts of Rajasthan",
    "Rani ki vav",
    "Great Himalayan National Park",
    "Nalanda Mahavihara",
    "Kapilvastu",
    "Dholavira",
    "Hoysala temples",

    # ── India: Major Heritage Sites (non-UNESCO) ───────────────────────────────
    "Konark Sun Temple",
    "Shore Temple",
    "Brihadisvara Temple",
    "Meenakshi Amman Temple",
    "Kailasa temple, Ellora",
    "Vittala Temple, Hampi",
    "Dilwara Temples",
    "Golden Temple",
    "Hawa Mahal",
    "City Palace, Jaipur",
    "Mysore Palace",
    "Amber Fort",
    "Mehrangarh",
    "Chittorgarh Fort",
    "Gwalior Fort",
    "Golconda Fort",
    "Bidar Fort",
    "Mandu, Madhya Pradesh",
    "Lothal",
    "Hampi",
    "Badami cave temples",
    "Belur Math",
    "Victoria Memorial, Kolkata",
    "Gateway of India",
    "India Gate",

    # ── South Asia ─────────────────────────────────────────────────────────────
    "Sigiriya",
    "Ancient City of Polonnaruwa",
    "Sacred City of Anuradhapura",
    "Dambulla cave temple",
    "Mohenjo-daro",
    "Taxila",
    "Rohtas Fort",
    "Lahore Fort",
    "Shalimar Gardens, Lahore",
    "Boudhanath",
    "Pashupatinath Temple",
    "Kathmandu Durbar Square",

    # ── Southeast Asia ─────────────────────────────────────────────────────────
    "Angkor Wat",
    "Angkor Thom",
    "Bayon temple",
    "Borobudur",
    "Prambanan",
    "Sukhothai Historical Park",
    "Ayutthaya Historical Park",
    "My Son sanctuary",
    "Hoi An Ancient Town",
    "Imperial Citadel of Thang Long",
    "Bagan",
    "Shwedagon Pagoda",
    "Luang Prabang",

    # ── East Asia ──────────────────────────────────────────────────────────────
    "Great Wall of China",
    "Forbidden City",
    "Temple of Heaven",
    "Summer Palace, Beijing",
    "Terracotta Army",
    "Mogao Caves",
    "Longmen Grottoes",
    "Yungang Grottoes",
    "Mount Tai",
    "West Lake",
    "Ancient City of Pingyao",
    "Potala Palace",
    "Lijiang Old Town",
    "Zhoukoudian",
    "Peking Man Site at Zhoukoudian",
    "Gyeongbokgung",
    "Bulguksa",
    "Seokguram",
    "Changdeokgung",
    "Hwaseong Fortress",
    "Himeji Castle",
    "Horyu-ji",
    "Itsukushima Shrine",
    "Nikkō Tōshō-gū",
    "Hiroshima Peace Memorial",

    # ── Middle East & Central Asia ─────────────────────────────────────────────
    "Petra",
    "Jerash",
    "Palmyra",
    "Persepolis",
    "Pasargadae",
    "Bishapur",
    "Ctesiphon",
    "Babylon",
    "Ur",
    "Ashur",
    "Hatra",
    "Samarkand",
    "Registan",
    "Shah-i-Zinda",
    "Bibi-Khanym Mosque",
    "Bukhara",
    "Khiva",
    "Ancient Merv",
    "Gonur Tepe",

    # ── Egypt & North Africa ───────────────────────────────────────────────────
    "Great Pyramid of Giza",
    "Egyptian pyramids",
    "Sphinx of Giza",
    "Karnak",
    "Luxor Temple",
    "Valley of the Kings",
    "Abu Simbel temples",
    "Dendera Temple complex",
    "Edfu",
    "Philae",
    "Alexandria",
    "Leptis Magna",
    "Carthage",
    "Volubilis",

    # ── Sub-Saharan Africa ─────────────────────────────────────────────────────
    "Great Zimbabwe",
    "Lalibela",
    "Aksum",
    "Timbuktu",
    "Djinguereber Mosque",
    "Robben Island",
    "Mapungubwe National Park",
    "Tsodilo",

    # ── Europe: Italy ──────────────────────────────────────────────────────────
    "Colosseum",
    "Pantheon, Rome",
    "Roman Forum",
    "Pompeii",
    "Herculaneum",
    "Acropolis of Athens",
    "Parthenon",
    "Palace of Knossos",
    "Delphi",
    "Olympia, Greece",
    "Epidaurus",
    "Florence Cathedral",
    "Piazza del Duomo, Pisa",
    "Venice",
    "Doge's Palace",
    "Castel del Monte",
    "Amalfi",
    "Hadrian's Wall",
    "Stonehenge",
    "Avebury",
    "Tower of London",
    "Palace of Westminster",
    "Versailles",
    "Mont-Saint-Michel",
    "Chartres Cathedral",
    "Notre-Dame de Paris",
    "Alhambra",
    "Sagrada Família",
    "Altamira cave",
    "Santiago de Compostela Cathedral",
    "Cologne Cathedral",
    "Neuschwanstein Castle",
    "Prague Castle",
    "Charles Bridge",
    "Auschwitz concentration camp",
    "Wieliczka Salt Mine",

    # ── Americas ───────────────────────────────────────────────────────────────
    "Machu Picchu",
    "Chan Chan",
    "Chavín de Huántar",
    "Tiwanaku",
    "Chichen Itza",
    "Teotihuacan",
    "Monte Albán",
    "Palenque",
    "Tikal",
    "Copán",
    "Statue of Liberty",
    "Independence Hall",
    "Mesa Verde National Park",
    "Cahokia",
    "Easter Island",

    # ── India: More Sites ──────────────────────────────────────────────────────
    "Brihadisvara Temple",
    "Konark Sun Temple",
    "Mahabalipuram",
    "Sanchi Stupa",
    "Elephanta Caves",
    "Badami cave temples",
    "Pattadakal",
    "Virupaksha Temple, Hampi",
    "Aihole",
    "Somnath temple",
    "Brihadeeswarar Temple",
    "Ramanathaswamy Temple",
    "Meenakshi Amman Temple",
    "Tirupati Balaji",
    "Lingaraja Temple",
    "Sun Temple, Modhera",
    "Rani ki vav",
    "Dholavira",
    "Nalanda",
    "Vikramashila",
    "Sarnath",
    "Kushinagar",
    "Lumbini",
    "Bodhgaya",
    "Varanasi",
    "Hampi",
    "Lepakshi",
    "Belur, Hassan district",
    "Halebidu",
    "Chitradurga Fort",
    "Bijapur, Karnataka",
    "Golconda",
    "Mandu, Madhya Pradesh",
    "Orchha",
    "Khajuraho",
    "Sanchi",
    "Udayagiri Caves",
    "Lothal",
    "Kalibangan",
    "Harappa",
    "Mohenjo-daro",

    # ── Historical Figures (for people-name queries) ───────────────────────────
    "Shah Jahan",
    "Akbar",
    "Ashoka",
    "Chandragupta Maurya",
    "Aurangzeb",
    "Babur",
    "Humayun",
    "Tipu Sultan",
    "Cleopatra",
    "Ramesses II",
    "Tutankhamun",
    "Julius Caesar",
    "Augustus",
    "Alexander the Great",
    "Genghis Khan",
    "Kublai Khan",
    "Saladin",
    "Suleiman the Magnificent",
    "Charlemagne",
    "Leonardo da Vinci",

    # ── Rivers & Natural Heritage ──────────────────────────────────────────────
    "Ganges",
    "Nile",
    "Tiber",
    "Euphrates",
    "Indus River",
    "Amazon River",
    "Yangtze River",
    "Mekong",
    "Jordan River",

    # ── More Global Sites ──────────────────────────────────────────────────────
    "Hagia Sophia",
    "Topkapi Palace",
    "Blue Mosque",
    "Ephesus",
    "Troy",
    "Göbekli Tepe",
    "Cappadocia",
    "Pamukkale",
    "Persepolis",
    "Isfahan",
    "Nasir al-Mulk Mosque",
    "Imam Mosque, Isfahan",
    "Dome of the Rock",
    "Church of the Holy Sepulchre",
    "Baalbek",
    "Lascaux",
    "Chauvet cave",
    "Newgrange",
    "Skara Brae",
    "Carcassonne",
    "Palace of the Popes",
    "Pont du Gard",
    "Dubrovnik",
    "Split, Croatia",
    "Diocletian's Palace",
    "Ephesus",
    "Mycenae",
    "Knossos",
    "Rhodes",
    "Acropolis of Athens",
    "Delphi",
    "Meteora",
    "Mystras",
    "Valletta",
    "Mdina",
    "Gozo",
    "Mdina",

    # ── Architecture & Art Styles ──────────────────────────────────────────────
    "Mughal architecture",
    "Dravidian architecture",
    "Indo-Islamic architecture",
    "Buddhist architecture",
    "Gothic architecture",
    "Romanesque architecture",
    "Byzantine architecture",
    "Islamic architecture",
    "Ancient Egyptian architecture",
    "Mesoamerican architecture",
    "Hindu temple architecture",
    "Jain architecture",
    "Sikh architecture",
    "Persian architecture",

    # ── Heritage Concepts ──────────────────────────────────────────────────────
    "World Heritage Site",
    "Archaeological Survey of India",
    "UNESCO",
    "Intangible cultural heritage",
    "Cultural landscape",
    "Historic preservation",
    "Archaeological site",
    "Ancient history",
    "Rock art",
    "Cave painting",
]

# Remove duplicates while preserving order
seen = set()
HERITAGE_ARTICLES_DEDUPED = []
for a in HERITAGE_ARTICLES:
    if a not in seen:
        seen.add(a)
        HERITAGE_ARTICLES_DEDUPED.append(a)


def fetch_article(title: str) -> dict | None:
    """Fetch a single Wikipedia article by exact title."""
    try:
        page = wikipedia.page(title, auto_suggest=False)
        return {
            "title": page.title,
            "url": page.url,
            "content": page.content,
            "summary": page.summary,
            "categories": page.categories,
            "query": title,          # exact title used as query
            "fetched_at": datetime.now().isoformat(),
            "source": "Wikipedia",
        }
    except wikipedia.exceptions.DisambiguationError as e:
        # Try first option
        try:
            page = wikipedia.page(e.options[0], auto_suggest=False)
            print(f"  ↳ Disambiguation → using '{e.options[0]}'")
            return {
                "title": page.title,
                "url": page.url,
                "content": page.content,
                "summary": page.summary,
                "categories": page.categories,
                "query": title,
                "fetched_at": datetime.now().isoformat(),
                "source": "Wikipedia",
            }
        except Exception:
            print(f"  ✗ Disambiguation fallback failed for: {title}")
            return None
    except Exception as e:
        print(f"  ✗ Error fetching '{title}': {e}")
        return None


def save_articles(articles: list, output_dir: str = "data/raw"):
    """Save each article as a numbered JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    saved = 0
    for i, article in enumerate(articles):
        safe_title = "".join(
            c for c in article["title"] if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        filename = f"{i+1:03d}_{safe_title[:50]}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(article, f, indent=2, ensure_ascii=False)
        saved += 1
    print(f"\n✓ Saved {saved} articles to {output_dir}/")


def main():
    print("=" * 60)
    print("HERITAGE DOCUMENT COLLECTOR — Curated Global Sites")
    print("=" * 60)
    print(f"Target articles : {len(HERITAGE_ARTICLES_DEDUPED)}")
    print("Starting...\n")

    articles = []
    failed = []

    for i, title in enumerate(HERITAGE_ARTICLES_DEDUPED, 1):
        print(f"[{i:>3}/{len(HERITAGE_ARTICLES_DEDUPED)}] {title}")
        article = fetch_article(title)
        if article:
            articles.append(article)
            print(f"  ✓ {article['title']}")
        else:
            failed.append(title)
        time.sleep(0.5)  # polite rate limit

    save_articles(articles)

    print("\n" + "=" * 60)
    print("COLLECTION COMPLETE")
    print("=" * 60)
    print(f"  Fetched : {len(articles)}")
    print(f"  Failed  : {len(failed)}")
    if failed:
        print("\nFailed titles:")
        for t in failed:
            print(f"  - {t}")


if __name__ == "__main__":
    main()

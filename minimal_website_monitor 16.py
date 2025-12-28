import sys
import logging
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from logging.handlers import RotatingFileHandler
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton,
    QVBoxLayout, QWidget, QLabel, QMessageBox
)
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, Qt
import json
import csv
import traceback
import re
import unicodedata

# Logging
handler = RotatingFileHandler('dashboard_errors.log', maxBytes=1024*1024, backupCount=5)
console_handler = logging.StreamHandler()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[handler, console_handler]
)
logger = logging.getLogger(__name__)

# Default thumbnail
DEFAULT_THUMBNAIL = "https://www.liberty-express.org/uploads/1/4/4/3/144388675/liberty-desk-2_orig.jpg"

# Thumbnails for key items (public domain / fair use)
THUMBNAIL_MAP = {
    "Home": DEFAULT_THUMBNAIL,
    "Welcome": DEFAULT_THUMBNAIL,
    "Liberty Blogs": DEFAULT_THUMBNAIL,
    "Navigate": DEFAULT_THUMBNAIL,
    "How Movies Are Made": DEFAULT_THUMBNAIL,
    "Playing Now 3": DEFAULT_THUMBNAIL,
    "The Chosen Adventures": "https://m.media-amazon.com/images/M/MV5BOGYwYTAxNzAtNDM3Ni00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyNTM3MDMyMDQ@._V1_.jpg",
    "Rumble Player": DEFAULT_THUMBNAIL,
    "Variety Television": "https://m.media-amazon.com/images/I/71nR1m9pZEL._AC_UF1000,1000_QL80_.jpg",
    "Control Hub": DEFAULT_THUMBNAIL,
    "Alex Jones And Editors Picks": "https://pbs.twimg.com/profile_images/378800000843072192/843072192.jpg",
    "Weekend Classics": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Liberty Free Movies": DEFAULT_THUMBNAIL,
    "Liberty Free Channel 1": DEFAULT_THUMBNAIL,
    "Liberty Free Channel 2": DEFAULT_THUMBNAIL,
    "Liberty Free Channel 3": DEFAULT_THUMBNAIL,
    "Classic Rewinds": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Rumble News": DEFAULT_THUMBNAIL,
    "Academy Awards Best Pictures 1927 2020": "https://m.media-amazon.com/images/M/MV5BMTc0MDMyMzI2OF5BMl5BanBnXkFtZTcwMzY2OTk0MQ@@._V1_.jpg",
    "Filmography Stanley Kubrick": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Roots Tv Series": "https://m.media-amazon.com/images/M/MV5BMTM3MDMyMDQ@._V1_.jpg",
    "Filmography Of Ken Russell": DEFAULT_THUMBNAIL,
    "The Nephilim Giants": "https://m.media-amazon.com/images/I/71nR1m9pZEL._AC_UF1000,1000_QL80_.jpg",
    "Monster Squad": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "All Dogs Go To Heaven": "https://m.media-amazon.com/images/M/MV5BMTY5Nzc4MDY@._V1_.jpg",
    "Mr Rogers Neighborhood": "https://m.media-amazon.com/images/I/71nR1m9pZEL._AC_UF1000,1000_QL80_.jpg",
    "Looney Tunes The Collectors Edition": "https://m.media-amazon.com/images/I/71nR1m9pZEL._AC_UF1000,1000_QL80_.jpg",
    "The Little Rascals Colorized": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Liberty Radio": DEFAULT_THUMBNAIL,
    "Sci Fi Channel": DEFAULT_THUMBNAIL,
    "Laurel And Hardy Colorized": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "50 Of The Greatest Cartoons": "https://m.media-amazon.com/images/I/71nR1m9pZEL._AC_UF1000,1000_QL80_.jpg",
    "Live News Livenow Fox 247 Live Stream": DEFAULT_THUMBNAIL,
    "British Classics": DEFAULT_THUMBNAIL,
    "Winnie The Pooh": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Father Ted": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Hogans Heros": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Classic Movies": DEFAULT_THUMBNAIL,
    "The Prisoner": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Red Dwarf": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Black Adder": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Western Classics": DEFAULT_THUMBNAIL,
    "Gunsmoke": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Fall Of The Maya Kings": DEFAULT_THUMBNAIL,
    "Dr Strangelove": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg",
    "Get Smart": "https://m.media-amazon.com/images/M/MV5BNjViMmRkOTEtM2M2OS00N2YxLWE2YzItM2U5ZDE0ZTI3ZTViXkEyXkFqcGdeQXVyMTY5Nzc4MDY@._V1_.jpg"
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<script src="/gdpr/gdprscript.js?buildTime=1766441351"></script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Liberty Express Command Center</title>
<style>
    html, body { height: 100%; margin: 0; padding: 0; }
    body { background: linear-gradient(to bottom, #1a0033, #000033); color: #ffffff; font-family: inherit !important; min-height: 100vh; display: flex; flex-direction: column; }
    header { background: rgba(0, 0, 0, 0.8); padding: 30px 20px; text-align: center; box-shadow: 0 4px 20px rgba(0, 255, 255, 0.3); }
    header h1 { margin: 0; font-size: 2.8em; font-weight: 600; letter-spacing: 1px; text-shadow: 0 0 15px #00ffff; }
    .search-bar { margin: 30px auto; width: 90%; max-width: 700px; }
    .search-bar input { width: 100%; padding: 18px 24px; font-size: 1.3em; border: 2px solid #00ffff; border-radius: 50px; background: rgba(0, 0, 0, 0.6); color: #ffffff; box-shadow: 0 0 20px rgba(0, 255, 255, 0.4); outline: none; font-family: inherit !important; }
    .filters { display: flex; justify-content: center; flex-wrap: wrap; gap: 10px; padding: 20px; }
    .filter-btn { padding: 8px 16px; background: rgba(0, 255, 255, 0.2); border: 1px solid #00ffff; border-radius: 20px; font-size: 0.9em; cursor: pointer; font-family: inherit !important; transition: all 0.3s; }
    .filter-btn.active { background: #00ffff; color: #000; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 25px; padding: 20px; flex: 1; }
    .card { background: #222222; border-radius: 16px; overflow: hidden; box-shadow: 0 8px 25px rgba(0, 0, 0, 0.6); display: flex; flex-direction: column; transition: transform 0.4s, box-shadow 0.4s; }
    .card:hover { transform: translateY(-12px); box-shadow: 0 20px 40px rgba(0, 255, 255, 0.4); }
    .card-thumbnail { width: 100%; height: 200px; object-fit: cover; border-bottom: 3px solid #00ffff; }
    .card-header { padding: 16px; background: rgba(0, 255, 255, 0.1); border-bottom: 1px solid rgba(0, 255, 255, 0.3); }
    .card-domain { font-size: 0.9em; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
    .card-title { padding: 16px 16px 8px; font-size: 1.4em; font-weight: 500; margin: 0; }
    .card-description { padding: 0 16px; font-size: 1em; opacity: 0.8; flex-grow: 1; }
    .card-tags { padding: 12px 16px 16px; display: flex; flex-wrap: wrap; gap: 8px; }
    .tag { padding: 4px 10px; background: rgba(0, 255, 255, 0.2); border-radius: 12px; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.5px; }
    .card-button { margin: 16px; padding: 14px; background: #00ffff; color: #000; text-align: center; font-weight: bold; border-radius: 12px; cursor: pointer; text-decoration: none; display: block; transition: background 0.3s; }
    .card-button:hover { background: #00e0e0; }
    footer { background: rgba(0, 0, 0, 0.8); padding: 15px; text-align: center; font-size: 0.9em; opacity: 0.8; }
</style>
</head>
<body>
<header>
    <h1>LIBERTY EXPRESS COMMAND CENTER</h1>
</header>
<div class="search-bar">
    <input type="text" id="search" placeholder="Search titles, descriptions, or tags..." aria-label="Search the catalog">
</div>
<div class="filters" id="filters" role="group" aria-label="Category filters"></div>
<div class="grid" id="grid" role="region" aria-label="Media catalog"></div>
<footer>Curated Freedom Media Portal - Updated: {update_date}</footer>

<script>
    const catalog = {data_json};
    const defaultThumbnail = "{default_thumbnail}";

    function createCard(item) {
        const card = document.createElement('div');
        card.className = 'card';

        const thumbnail = document.createElement('img');
        thumbnail.className = 'card-thumbnail';
        thumbnail.src = item.thumbnail || defaultThumbnail;
        thumbnail.alt = item.title + " thumbnail";
        thumbnail.loading = "lazy";
        card.appendChild(thumbnail);

        const header = document.createElement('div');
        header.className = 'card-header';
        const domain = document.createElement('div');
        domain.className = 'card-domain';
        domain.textContent = item.domain;
        header.appendChild(domain);
        card.appendChild(header);

        const title = document.createElement('h2');
        title.className = 'card-title';
        title.textContent = item.title;
        card.appendChild(title);

        const desc = document.createElement('p');
        desc.className = 'card-description';
        desc.textContent = item.description;
        card.appendChild(desc);

        const tagsDiv = document.createElement('div');
        tagsDiv.className = 'card-tags';
        item.subjects.forEach(subject => {
            const tag = document.createElement('span');
            tag.className = 'tag';
            tag.textContent = subject;
            tagsDiv.appendChild(tag);
        });
        card.appendChild(tagsDiv);

        const button = document.createElement('a');
        button.className = 'card-button';
        button.href = item.url;
        button.target = "_blank";
        button.rel = "noopener noreferrer";
        button.textContent = "OPEN LINK";
        button.setAttribute('aria-label', 'Open ' + item.title);
        card.appendChild(button);

        return card;
    }

    function renderCatalog(items) {
        const grid = document.getElementById('grid');
        grid.innerHTML = '';
        items.forEach(item => {
            grid.appendChild(createCard(item));
        });
    }

    function populateFilters() {
        const filtersDiv = document.getElementById('filters');
        const domains = [...new Set(catalog.items.map(i => i.domain))].sort();
        domains.forEach(domain => {
            const btn = document.createElement('button');
            btn.className = 'filter-btn';
            btn.textContent = domain;
            btn.setAttribute('aria-pressed', 'false');
            btn.onclick = () => {
                btn.classList.toggle('active');
                btn.setAttribute('aria-pressed', btn.classList.contains('active'));
                filterCatalog();
            };
            filtersDiv.appendChild(btn);
        });
    }

    function filterCatalog() {
        const activeDomains = Array.from(document.querySelectorAll('.filter-btn.active')).map(b => b.textContent);
        const searchTerm = document.getElementById('search').value.toLowerCase().trim();

        let filtered = catalog.items;

        if (activeDomains.length > 0) {
            filtered = filtered.filter(item => activeDomains.includes(item.domain));
        }

        if (searchTerm) {
            filtered = filtered.filter(item =>
                item.title.toLowerCase().includes(searchTerm) ||
                item.description.toLowerCase().includes(searchTerm) ||
                item.subjects.some(s => s.toLowerCase().includes(searchTerm))
            );
        }

        renderCatalog(filtered);
    }

    document.getElementById('search').addEventListener('input', filterCatalog);
    populateFilters();
    renderCatalog(catalog.items);
</script>
</body>
</html>"""

def unicode_to_ascii(text):
    """Convert mathematical bold/fraktur/script etc. Unicode to regular ASCII equivalents."""
    return ''.join(
        chr(ord(c) - 0x1D400 + ord('A')) if 0x1D400 <= ord(c) <= 0x1D433 else
        chr(ord(c) - 0x1D434 + ord('a')) if 0x1D434 <= ord(c) <= 0x1D467 else
        chr(ord(c) - 0x1D56C + ord('A')) if 0x1D56C <= ord(c) <= 0x1D59F else
        chr(ord(c) - 0x1D5A0 + ord('a')) if 0x1D5A0 <= ord(c) <= 0x1D5D3 else
        c
        for c in text
    )

class WebsiteMonitor(QObject):
    update_detected = pyqtSignal(str, str, list, dict)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.last_hash = None
        self.retry_count = 0
        self.max_retries = 5

    def normalize_title(self, text):
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)
        text = unicode_to_ascii(text)
        text = unicodedata.normalize('NFKC', text)
        text = text.replace("SEIRES", "Series").replace("EVERTYTHING", "Everything").replace("FREINDS", "Friends")
        text = text.replace(" And ", " and ").replace(" Of ", " of ")
        text = re.sub(r'[^a-zA-Z0-9\s&\'\-:]', '', text)
        if text.isupper() and len(text) > 3:
            text = text.title()
        return text.strip()

    def assign_domain_and_subjects(self, title):
        title_lower = title.lower()
        if any(k in title_lower for k in ["blog", "article", "news", "rumble news", "alex jones"]):
            return "News / Commentary", ["News", "Commentary"]
        elif any(k in title_lower for k in ["movie", "film", "classic", "cinema", "awards", "kubrick", "russell", "strangelove"]):
            return "Movies / Cinema", ["Movies", "Classics"]
        elif any(k in title_lower for k in ["tv", "television", "series", "show", "channel", "chosen", "roots", "prisoner", "red dwarf"]):
            return "TV Series / Channels", ["TV", "Series"]
        elif any(k in title_lower for k in ["cartoon", "looney", "pooh", "rascals", "dogs go to heaven", "laurel", "hardy"]):
            return "Cartoons / Animation", ["Cartoons", "Animation"]
        elif any(k in title_lower for k in ["radio", "live news", "fox"]):
            return "Radio / Live News", ["Radio", "Live"]
        elif any(k in title_lower for k in ["western", "gunsmoke", "classic movies"]):
            return "Westerns", ["Westerns"]
        elif any(k in title_lower for k in ["sci fi", "science fiction"]):
            return "Science Fiction", ["Sci-Fi"]
        elif "british" in title_lower:
            return "British Classics", ["British"]
        else:
            return "Tools / Utilities", ["Navigation"]

    def generate_description(self, title, domain):
        base = {
            "News / Commentary": "Latest news, commentary, and independent media.",
            "Movies / Cinema": "Feature films, classics, and cinematic masterpieces.",
            "TV Series / Channels": "Television series, channels, and episodic content.",
            "Cartoons / Animation": "Animated series and classic cartoons.",
            "Radio / Live News": "Live radio streams and news broadcasts.",
            "Westerns": "Classic western films and series.",
            "Science Fiction": "Sci-fi movies and television.",
            "British Classics": "Iconic British television and comedy.",
            "Tools / Utilities": "Navigation and portal tools.",
            "Archives & Collections": "Curated media collection."
        }.get(domain, "Curated media content.")
        if 'alex jones' in title.lower():
            return "Curated selection by Alex Jones and editors."
        return base

    def extract_and_enrich(self):
        try:
            r = requests.get(self.url, timeout=20, headers=self.headers)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            uls = soup.find_all('ul')
            if not uls:
                logger.warning("No <ul> elements found")
                return []
            main = max(uls, key=lambda u: len(u.find_all('a', href=True)))
            items = []
            seen_titles = set()
            for a in main.find_all('a', href=True):
                raw = a.get_text(strip=True)
                if raw:
                    url = urljoin(self.url, a['href'])
                    title = self.normalize_title(raw)
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    domain, subs = self.assign_domain_and_subjects(title)
                    desc = self.generate_description(title, domain)
                    thumbnail = THUMBNAIL_MAP.get(title, DEFAULT_THUMBNAIL)
                    items.append({"title": title, "url": url, "domain": domain, "subjects": subs, "description": desc, "thumbnail": thumbnail})
            if items and items[0]["title"] != "Home":
                items.insert(0, {"title": "Home", "url": self.url, "domain": "Tools / Utilities", "subjects": ["Navigation"], "description": "Main portal for Liberty Express.", "thumbnail": DEFAULT_THUMBNAIL})
            logger.info(f"Extracted {len(items)} unique cleaned items with thumbnails")
            return items
        except Exception as e:
            logger.error(f"Extract error: {traceback.format_exc()}")
            return []

    def check_website(self):
        try:
            items = self.extract_and_enrich()
            if not items:
                self.retry_count += 1
                logger.warning(f"Retry {self.retry_count}/{self.max_retries}")
                if self.retry_count <= self.max_retries:
                    delay = min(10000 * self.retry_count, 60000)
                    QTimer.singleShot(delay, self.check_website)
                return

            content = "".join(f"{i['title']}{i['url']}{i['domain']}" for i in items)
            h = hashlib.md5(content.encode()).hexdigest()
            if h != self.last_hash:
                self.last_hash = h
                now = datetime.now().strftime("%B %d, %Y at %H:%M")
                catalog = {"items": items}
                self.update_detected.emit(self.url, f"UPDATE! {len(items)} items", items, catalog)
                self.generate_all(catalog, now)
                logger.info("Files auto-saved on change")
            self.retry_count = 0
        except Exception as e:
            logger.error(f"Check error: {traceback.format_exc()}")

    def generate_all(self, catalog, date):
        try:
            self.save_json(catalog, date)
            self.save_csv(catalog, date)
            self.save_html(catalog, date)
            logger.info("All files generated")
        except Exception as e:
            logger.error(f"Generate error: {traceback.format_exc()}")

    def save_json(self, catalog, date):
        try:
            catalog["updated"] = date
            with open("liberty-catalog.json", "w", encoding="utf-8") as f:
                json.dump(catalog, f, indent=2)
            logger.info("Saved liberty-catalog.json")
        except Exception as e:
            logger.error(f"JSON save error: {traceback.format_exc()}")

    def save_csv(self, catalog, date):
        try:
            with open("liberty-catalog.csv", "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Updated", date])
                w.writerow(["Title", "URL", "Domain", "Subjects", "Description", "Thumbnail"])
                for i in catalog["items"]:
                    w.writerow([i["title"], i["url"], i["domain"], "; ".join(i["subjects"]), i["description"], i.get("thumbnail", "")])
            logger.info("Saved liberty-catalog.csv")
        except Exception as e:
            logger.error(f"CSV save error: {traceback.format_exc()}")

    def save_html(self, catalog, date):
        try:
            html = HTML_TEMPLATE.format(
                update_date=date,
                default_thumbnail=DEFAULT_THUMBNAIL,
                data_json=json.dumps(catalog, indent=2)
            )
            with open("liberty-command-center.html", "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("Saved liberty-command-center.html")
        except Exception as e:
            logger.error(f"HTML save error: {traceback.format_exc()}")

class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.monitor = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Liberty Express Generator")
        self.resize(500, 300)

        central = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("LIBERTY EXPRESS\nCOMMAND CENTER GENERATOR")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #00ffff; text-align: center;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.status = QLabel("Ready – Press button to scan site and generate all files")
        self.status.setStyleSheet("font-size: 16px; color: #ffffff; text-align: center;")
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        btn = QPushButton("SCAN SITE & SAVE ALL FILES")
        btn.setStyleSheet("""
            QPushButton {
                padding: 20px;
                font-size: 20px;
                font-weight: bold;
                background-color: #00ffff;
                color: black;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #00e0e0;
            }
        """)
        btn.clicked.connect(self.generate)
        layout.addWidget(btn)

        central.setLayout(layout)
        self.setCentralWidget(central)

        self.monitor = WebsiteMonitor("https://www.liberty-express.org/")
        self.monitor.update_detected.connect(self.on_update)
        QTimer.singleShot(3000, self.monitor.check_website)

    def generate(self):
        try:
            self.status.setText("Scanning site...")
            QApplication.processEvents()
            items = self.monitor.extract_and_enrich()
            if not items:
                self.status.setText("Failed – no links found")
                QMessageBox.warning(self, "Error", "No links extracted. Check logs.")
                return

            now = datetime.now().strftime("%B %d, %Y at %H:%M")
            catalog = {"items": items}
            self.monitor.generate_all(catalog, now)

            self.status.setText(f"Success! {len(items)} items saved")
            QMessageBox.information(self, "Complete", 
                f"All files generated:\n"
                f"• liberty-command-center.html (with cleaned titles & thumbnails!)\n"
                f"• liberty-catalog.json\n"
                f"• liberty-catalog.csv")
        except Exception as e:
            logger.error(f"Manual generate crash: {traceback.format_exc()}")
            self.status.setText("Error – check logs")
            QMessageBox.critical(self, "Crash", "Error during generation. Check dashboard_errors.log")

    def on_update(self, url, text, items, catalog):
        try:
            self.status.setText(f"{text} – Files saved")
            QMessageBox.information(self, "Auto Update", text + "\nFiles refreshed.")
        except Exception as e:
            logger.error(f"on_update error: {traceback.format_exc()}")

def main():
    try:
        app = QApplication(sys.argv)
        win = DashboardWindow()
        win.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Startup crash: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
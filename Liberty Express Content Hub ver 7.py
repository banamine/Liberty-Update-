# ============================================================================
# LIBERTY EXPRESS CONTENT HUB - WITH CUSTOM OUTPUT DIRECTORY
# ============================================================================

import sys
import logging
import hashlib
import requests
import webbrowser
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from logging.handlers import RotatingFileHandler
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton,
    QVBoxLayout, QWidget, QLabel, QMessageBox,
    QDialog, QListWidget, QScrollArea, QHBoxLayout,
    QGridLayout, QLineEdit, QCheckBox, QGroupBox,
    QProgressBar, QStatusBar
)
from PyQt6.QtCore import (
    QTimer, QObject, pyqtSignal, Qt, QThread,
    QMutex, QWaitCondition, QReadWriteLock, QLockFile,
    QCoreApplication
)
from PyQt6.QtGui import QFont, QIcon, QAction
import json
import os
import csv
import traceback
import re
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any, Set, Union
from enum import Enum
from string import Template
import html
import time

# ============================================================================
# CONFIGURATION & LOGGING
# ============================================================================

def setup_logging():
    """Configure logging with rotation and file validation"""
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, 'dashboard_errors.log')
    
    handler = RotatingFileHandler(
        log_file, 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=10,
        encoding='utf-8'
    )
    
    console_handler = logging.StreamHandler()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s',
        handlers=[handler, console_handler]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

def load_config(config_path="config.json") -> Dict:
    """Safely load configuration from external file with validation"""
    default_config = {
        "classification_patterns": {
            "live_tv": ["live", "now playing", "streaming now", "radio", "news", "rumble"],
            "series": ["series", "season", "episode", "tv show", "comedy series"],
            "movies": ["movie", "film", "cinema", "classic", "feature"],
            "kids": ["kids", "children", "cartoon", "animation", "family", "pooh"],
            "documentary": ["documentary", "docu", "education", "history"],
            "westerns": ["western", "cowboy", "gunsmoke", "cheyenne"],
            "scifi": ["sci-fi", "science fiction", "fantasy", "space"],
            "comedy": ["comedy", "funny", "humor"],
            "news": ["news", "current", "alex jones", "epoch"],
            "radio": ["radio", "podcast", "audio", "talk"],
            "tools": ["control", "hub", "tools", "settings", "player"]
        },
        "tag_patterns": {
            "comedy": ["comedy", "funny", "humor", "sitcom"],
            "western": ["western", "cowboy", "ranch", "frontier"],
            "scifi": ["sci-fi", "space", "alien", "future", "robot"],
            "classic": ["classic", "vintage", "retro", "old", "golden age"],
            "british": ["british", "uk", "england", "bbc"],
            "animated": ["animated", "cartoon", "animation"],
            "live": ["live", "streaming", "now playing"],
            "series": ["series", "season", "episode"],
            "movie": ["movie", "film", "feature"],
            "kids": ["kids", "children", "family"],
            "documentary": ["documentary", "docu", "educational"]
        },
        "featured_keywords": ["now playing", "featured", "spotlight", "new", "latest"],
        "live_keywords": ["live", "streaming now", "now playing"],
        "kids_keywords": ["kids", "children", "family", "cartoon", "pooh", "looney tunes"],
        "series_keywords": ["series", "season", "episode", "tv show"],
        "decade_patterns": ["19\\d0s", "20\\d0s"],
        "thumbnail_config": {
            "placeholder_base": "https://via.placeholder.com/200x120/",
            "category_colors": {
                "live_tv": "FF0000/FFFFFF?text=LIVE",
                "series": "4285F4/FFFFFF?text=SERIES",
                "movies": "EA4335/FFFFFF?text=MOVIE",
                "kids": "34A853/FFFFFF?text=KIDS",
                "documentary": "9C27B0/FFFFFF?text=DOC",
                "westerns": "FF9800/FFFFFF?text=WEST",
                "scifi": "00BCD4/FFFFFF?text=SCI-FI",
                "default": "666666/FFFFFF?text=CONTENT"
            }
        },
        "output_directory": "output",  # <-- new
        "extraction": {
            "main_ul_selector": "ul",  # CSS selector fallback
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "timeout": 30,
            "retries": 3
        }
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Deep merge with validation (simplified here)
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
                logger.info(f"Loaded configuration from {config_path}")
    except Exception as e:
        logger.warning(f"Failed to load config file, using defaults: {e}")
    
    return default_config

CONFIG = load_config()

# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class ContentHubError(Exception):
    """Base exception for content hub errors"""
    pass

class NetworkError(ContentHubError):
    """Raised when network operations fail"""
    pass

class ExtractionError(ContentHubError):
    """Raised when content extraction fails"""
    pass

class FileOperationError(ContentHubError):
    """Raised when file operations fail"""
    pass

# ============================================================================
# THREAD SAFETY UTILITIES (using Qt's QLockFile)
# ============================================================================

class FileLock:
    """Cross-platform file locking using QLockFile"""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.lockfile_path = filepath + '.lock'
        self.lock = QLockFile(self.lockfile_path)
        # Set stale lock timeout to 30 seconds
        self.lock.setStaleLockTime(30000)
        
    def __enter__(self):
        if not self.lock.tryLock(5000):  # Wait up to 5 seconds
            raise FileOperationError(f"Cannot acquire lock for {self.filepath}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.unlock()

def safe_file_write(filepath: str, content: str, mode: str = 'w'):
    """Thread-safe file writing with directory validation"""
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    with FileLock(filepath):
        with open(filepath, mode, encoding='utf-8') as f:
            f.write(content)

def safe_file_read(filepath: str) -> Optional[str]:
    """Thread-safe file reading"""
    if not os.path.exists(filepath):
        return None
    
    with FileLock(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

# ============================================================================
# DATA MODELS
# ============================================================================

class ContentType(Enum):
    LIVE_TV = "Live TV / Streams"
    SERIES = "Series"
    MOVIES = "Movies"
    KIDS = "Kids & Family"
    DOCUMENTARY = "Documentaries"
    RADIO = "Radio & Podcasts"
    SPECIAL = "Special Collections"
    TOOLS = "Tools / Control Hub"
    NEWS = "News & Current Events"
    CLASSICS = "Classic Cinema"
    WESTERNS = "Westerns"
    COMEDY = "Comedy"
    SCIFI = "Sci-Fi & Fantasy"

@dataclass
class LinkItem:
    id: str
    title: str
    url: str
    display_title: str
    description: str
    category: ContentType
    subcategory: str = ""
    tags: List[str] = field(default_factory=list)
    thumbnail: str = ""
    decade: str = ""
    is_featured: bool = False
    is_live: bool = False
    is_kidsafe: bool = False
    is_series: bool = False
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "display_title": self.display_title,
            "description": self.description,
            "category": self.category.value,
            "subcategory": self.subcategory,
            "tags": self.tags,
            "thumbnail": self.thumbnail,
            "decade": self.decade,
            "is_featured": self.is_featured,
            "is_live": self.is_live,
            "is_kidsafe": self.is_kidsafe,
            "is_series": self.is_series
        }

@dataclass
class ContentSection:
    name: str
    category: ContentType
    description: str
    items: List[LinkItem] = field(default_factory=list)
    icon: str = ""
    is_collapsible: bool = True
    default_expanded: bool = False
    subcategories: List[str] = field(default_factory=list)
    is_kidsafe: bool = False
    decade: str = ""
    
    def add_item(self, item: LinkItem):
        self.items.append(item)
    
    def to_dict(self):
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "icon": self.icon,
            "is_collapsible": self.is_collapsible,
            "default_expanded": self.default_expanded,
            "subcategories": self.subcategories,
            "is_kidsafe": self.is_kidsafe,
            "decade": self.decade,
            "items": [item.to_dict() for item in self.items]
        }

# ============================================================================
# CONTENT MANAGER (encapsulates classification logic)
# ============================================================================

class ContentManager:
    """Handles classification and organization of content items"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.lock = QReadWriteLock()
        self.sections: Dict[str, ContentSection] = {}
        self._setup_default_sections()
    
    def _setup_default_sections(self):
        """Initialize default content sections"""
        for content_type in ContentType:
            section = ContentSection(
                name=content_type.value,
                category=content_type,
                description=f"{content_type.value} content"
            )
            self.sections[content_type.name] = section
    
    def classify_item(self, title: str, url: str, description: str = "") -> LinkItem:
        """Classify a single link item based on title and URL"""
        self.lock.lockForRead()
        try:
            patterns = self.config.get("classification_patterns", {})
            title_lower = title.lower()
            
            # Determine category
            category = ContentType.TOOLS  # default
            for cat_name, keywords in patterns.items():
                if any(kw in title_lower for kw in keywords):
                    try:
                        category = ContentType[cat_name.upper()]
                        break
                    except KeyError:
                        continue
            
            # Extract decade if present
            decade = ""
            for pattern in self.config.get("decade_patterns", []):
                match = re.search(pattern, title)
                if match:
                    decade = match.group()
                    break
            
            # Generate tags
            tags = []
            for tag_name, tag_keywords in self.config.get("tag_patterns", {}).items():
                if any(kw in title_lower for kw in tag_keywords):
                    tags.append(tag_name)
            
            # Determine flags
            is_featured = any(kw in title_lower for kw in self.config.get("featured_keywords", []))
            is_live = any(kw in title_lower for kw in self.config.get("live_keywords", []))
            is_kidsafe = any(kw in title_lower for kw in self.config.get("kids_keywords", []))
            is_series = any(kw in title_lower for kw in self.config.get("series_keywords", []))
        finally:
            self.lock.unlock()
        
        # Create item ID
        item_id = hashlib.md5(f"{title}{url}".encode()).hexdigest()[:8]
        
        return LinkItem(
            id=item_id,
            title=title,
            url=url,
            display_title=title,
            description=description,
            category=category,
            decade=decade,
            tags=tags,
            is_featured=is_featured,
            is_live=is_live,
            is_kidsafe=is_kidsafe,
            is_series=is_series
        )
    
    def organize_items(self, items: List[LinkItem]) -> Dict[str, ContentSection]:
        """Organize items into sections by category"""
        self.lock.lockForWrite()
        try:
            # Reset sections
            self._setup_default_sections()
            
            for item in items:
                cat_name = item.category.name
                if cat_name in self.sections:
                    self.sections[cat_name].add_item(item)
                else:
                    # Fallback to a misc section
                    misc_section = self.sections.get("TOOLS", ContentSection("Misc", ContentType.TOOLS, "Miscellaneous"))
                    misc_section.add_item(item)
            
            return self.sections
        finally:
            self.lock.unlock()
    
    def get_data_for_html(self) -> Dict:
        """Prepare data structure for HTML export"""
        self.lock.lockForRead()
        try:
            sections_dict = {
                name: section.to_dict() 
                for name, section in self.sections.items() 
                if section.items  # only include non-empty sections
            }
            all_tags = list(set(tag for section in self.sections.values() for item in section.items for tag in item.tags))
            return {
                "sections": sections_dict,
                "all_tags": all_tags,
                "total_items": sum(len(s.items) for s in self.sections.values())
            }
        finally:
            self.lock.unlock()

# ============================================================================
# THREADED WORKERS
# ============================================================================

class ExtractionWorker(QThread):
    """Background worker for website extraction with retry logic"""
    progress = pyqtSignal(int, str)  # percentage, message
    finished = pyqtSignal(list, dict)  # raw_links, organized_data
    error = pyqtSignal(str)
    
    def __init__(self, url: str, config: Dict, content_manager: ContentManager):
        super().__init__()
        self.url = url
        self.config = config
        self.content_manager = content_manager
        self.is_running = True
        
    def run(self):
        """Main extraction logic with retries"""
        try:
            self.progress.emit(0, "Starting extraction...")
            
            # Step 1: Fetch website with retries
            self.progress.emit(10, "Fetching website content...")
            html_content = self._fetch_with_retries()
            if not self.is_running:
                return
            
            # Step 2: Parse HTML
            self.progress.emit(30, "Parsing HTML content...")
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Step 3: Extract links
            self.progress.emit(50, "Extracting links...")
            raw_links = self._extract_links(soup)
            
            if not self.is_running:
                return
            
            if not raw_links:
                self.error.emit("No content found on page")
                return
            
            # Step 4: Classify and organize using ContentManager
            self.progress.emit(70, "Classifying content...")
            items = []
            for text, url in raw_links:
                if not self.is_running:
                    return
                item = self.content_manager.classify_item(text, url)
                items.append(item)
            
            organized_sections = self.content_manager.organize_items(items)
            organized_data = self.content_manager.get_data_for_html()
            
            self.progress.emit(100, "Extraction complete!")
            self.finished.emit(raw_links, organized_data)
            
        except NetworkError as e:
            self.error.emit(f"Network error after retries: {str(e)}")
        except ExtractionError as e:
            self.error.emit(f"Extraction error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected extraction error: {traceback.format_exc()}")
            self.error.emit(f"Unexpected error: {str(e)}")
    
    def _fetch_with_retries(self) -> str:
        """Fetch URL with exponential backoff retries"""
        max_retries = self.config.get("extraction", {}).get("retries", 3)
        timeout = self.config.get("extraction", {}).get("timeout", 30)
        user_agent = self.config.get("extraction", {}).get("user_agent", 
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    self.url, 
                    timeout=timeout, 
                    headers={'User-Agent': user_agent}
                )
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise NetworkError(f"Failed after {max_retries} attempts: {e}")
                wait = 2 ** attempt  # exponential backoff
                self.progress.emit(10 + attempt*5, f"Retry {attempt+1} in {wait}s...")
                time.sleep(wait)
                if not self.is_running:
                    raise NetworkError("Cancelled by user")
    
    def _extract_links(self, soup: BeautifulSoup) -> List[tuple]:
        """Extract links from the webpage using configurable selectors"""
        candidates = soup.find_all('ul')
        if not candidates:
            raise ExtractionError("No <ul> elements found on page")
        
        # Find the UL with most links (likely main navigation)
        main_ul = max(candidates, key=lambda u: len(u.find_all('a', href=True)))
        
        raw_links = []
        for a in main_ul.find_all('a', href=True):
            text = a.get_text(strip=True)
            if text:
                full_url = urljoin(self.url, a['href'])
                raw_links.append((text, full_url))
        
        # Add HOME at top if not present
        if raw_links and "HOME" not in raw_links[0][0].upper():
            raw_links.insert(0, ("HOME", self.url))
        
        return raw_links
    
    def stop(self):
        """Gracefully stop the worker"""
        self.is_running = False
        self.wait(5000)  # Wait up to 5 seconds

class FileSaveWorker(QThread):
    """Background worker for file operations with error handling"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)  # filename
    error = pyqtSignal(str)
    
    def __init__(self, file_type: str, data: Any, metadata: Dict, output_dir: str):
        super().__init__()
        self.file_type = file_type
        self.data = data
        self.metadata = metadata
        self.output_dir = output_dir   # <-- store
        
    def run(self):
        """Save files in background thread with proper error handling"""
        try:
            self.progress.emit(0, f"Saving {self.file_type}...")
            
            if self.file_type == "html":
                filename = self._save_html()
            elif self.file_type == "json":
                filename = self._save_json()
            elif self.file_type == "csv":
                filename = self._save_csv()
            else:
                raise ValueError(f"Unknown file type: {self.file_type}")
            
            self.progress.emit(100, f"Saved {filename}")
            self.finished.emit(filename)
            
        except FileOperationError as e:
            logger.error(f"File operation error: {traceback.format_exc()}")
            self.error.emit(f"File error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected file save error: {traceback.format_exc()}")
            self.error.emit(f"Unexpected error: {str(e)}")
    
    def _save_html(self) -> str:
        """Generate and save static HTML content hub"""
        filename = os.path.join(self.output_dir, "liberty-content-hub.html")
        html_content = generate_safe_html(self.data, self.metadata.get("updated", ""))
        safe_file_write(filename, html_content)
        return filename
    
    def _save_json(self) -> str:
        """Save JSON data with proper encoding"""
        filename = os.path.join(self.output_dir, "liberty-content-library.json")
        safe_file_write(filename, json.dumps(self.data, indent=2, default=str))
        return filename
    
    def _save_csv(self) -> str:
        """Save CSV data with all fields flattened"""
        filename = os.path.join(self.output_dir, "liberty-content-index.csv")
        
        # Flatten items into rows
        rows = []
        for section_name, section in self.data.get("sections", {}).items():
            for item in section.get("items", []):
                row = {
                    "section": section_name,
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "category": item.get("category", ""),
                    "tags": ", ".join(item.get("tags", [])),
                    "description": item.get("description", ""),
                    "thumbnail": item.get("thumbnail", ""),
                    "decade": item.get("decade", ""),
                    "is_featured": item.get("is_featured", False),
                    "is_live": item.get("is_live", False),
                    "is_kidsafe": item.get("is_kidsafe", False)
                }
                rows.append(row)
        
        # Write CSV with locking
        with FileLock(filename):
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
        return filename

# ============================================================================
# SAFE HTML TEMPLATE (STATIC GENERATION)
# ============================================================================

def generate_safe_html(data: Dict, update_date: str) -> str:
    """Generate a fully static HTML page with all links and placeholders embedded."""
    sections_html = ""
    for section_name, section in data.get("sections", {}).items():
        items_html = ""
        for item in section.get("items", []):
            title = html.escape(item.get("display_title", ""))
            url = html.escape(item.get("url", ""))
            tags = ", ".join(html.escape(tag) for tag in item.get("tags", []))
            items_html += f'''
                <div class="item">
                    <a href="{url}" target="_blank">{title}</a>
                    <div class="tags">{tags}</div>
                </div>
            '''
        sections_html += f'''
            <div class="section">
                <h2>{html.escape(section.get("name", ""))}</h2>
                <p>{html.escape(section.get("description", ""))}</p>
                {items_html}
            </div>
        '''

    return f'''<!DOCTYPE html>
<html>
<head>
    <title>Liberty Express Content Hub</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #0a001a;
            color: white;
            margin: 0;
            padding: 20px;
        }}
        h1 {{
            color: #00ffff;
            text-align: center;
        }}
        .section {{
            margin: 20px 0;
            padding: 15px;
            background: rgba(26,26,46,0.8);
            border-radius: 8px;
        }}
        .section h2 {{
            color: #00ffff;
            margin-top: 0;
        }}
        .item {{
            display: inline-block;
            margin: 10px;
            padding: 10px;
            background: #1a1a2e;
            border-radius: 6px;
            text-align: center;
        }}
        .item a {{
            color: #00ffff;
            text-decoration: none;
            font-weight: bold;
        }}
        .item a:hover {{
            text-decoration: underline;
        }}
        .tags {{
            font-size: 0.8em;
            color: #aaa;
            margin-top: 5px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>Liberty Express Content Hub</h1>
    <p style="text-align: center;">Updated: {html.escape(update_date)}</p>
    <div id="content">
        {sections_html}
    </div>
    <div class="footer">Generated by Liberty Express Content Manager</div>
</body>
</html>'''

# ============================================================================
# MAIN APPLICATION WINDOW
# ============================================================================

class DashboardWindow(QMainWindow):
    """Main application window with improved thread management"""
    
    def __init__(self):
        super().__init__()
        self.config = CONFIG
        self.content_manager = ContentManager(self.config)
        # Set up output directory
        self.output_dir = os.path.abspath(self.config.get("output_directory", "output"))
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir}")
        
        self.workers: List[QThread] = []
        self.is_processing = False
        self.setup_ui()
        self.setup_monitors()
    
    def setup_ui(self):
        """Initialize the user interface"""
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # Header
        header = QLabel("Liberty Express Content Manager")
        header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #00ffff; padding: 15px; background: rgba(0,0,0,0.7); border-radius: 8px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Progress indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        main_layout.addWidget(self.progress_bar)
        
        # URL input field
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Source URL:"))
        self.url_input = QLineEdit("https://www.liberty-express.org/")
        self.url_input.setPlaceholderText("Enter website URL to extract")
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)
        
        # Control Panel
        control_panel = QGroupBox("Control Panel")
        control_layout = QGridLayout()
        
        self.btn_generate = QPushButton("🔄 Generate Content Hub")
        self.btn_generate.clicked.connect(self.generate_content_hub)
        self.btn_generate.setToolTip("Extract and organize content (runs in background)")
        
        self.btn_export = QPushButton("📁 Export All Formats")
        self.btn_export.clicked.connect(self.export_all_formats)
        
        self.btn_view = QPushButton("📊 View Content Library")
        self.btn_view.clicked.connect(self.view_content_library)
        
        self.btn_stop = QPushButton("⏹️ Stop Processing")
        self.btn_stop.clicked.connect(self.stop_processing)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #FF4444;")
        
        control_layout.addWidget(self.btn_generate, 0, 0)
        control_layout.addWidget(self.btn_export, 0, 1)
        control_layout.addWidget(self.btn_view, 1, 0)
        control_layout.addWidget(self.btn_stop, 1, 1)
        
        control_panel.setLayout(control_layout)
        main_layout.addWidget(control_panel)
        
        # Stats Panel
        self.stats_panel = self.create_stats_panel()
        main_layout.addWidget(self.stats_panel)
        
        # Monitor Status
        self.monitor_status = QLabel("Monitoring not started")
        self.monitor_status.setStyleSheet("""
            padding: 10px; 
            background: rgba(26,26,46,0.8); 
            border-radius: 5px;
            font-family: monospace;
        """)
        main_layout.addWidget(self.monitor_status)
        
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        self.setWindowTitle("Liberty Express Content Hub Manager")
        self.resize(1000, 600)
        
        # Update stats timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats_from_manager)
        self.stats_timer.start(3000)
    
    def create_stats_panel(self) -> QGroupBox:
        """Create statistics panel"""
        panel = QGroupBox("Content Statistics")
        layout = QHBoxLayout()
        
        self.lbl_items = QLabel("Items: 0")
        self.lbl_sections = QLabel("Sections: 0")
        self.lbl_tags = QLabel("Tags: 0")
        self.lbl_last_update = QLabel("Last: Never")
        
        layout.addWidget(self.lbl_items)
        layout.addWidget(self.lbl_sections)
        layout.addWidget(self.lbl_tags)
        layout.addWidget(self.lbl_last_update)
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
    
    def setup_monitors(self):
        """Setup website monitors with proper threading"""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_websites)
        self.monitor_timer.start(30000)
        QTimer.singleShot(5000, self.check_websites)
    
    def check_websites(self):
        """Check websites for updates (non-blocking)"""
        if self.is_processing:
            logger.info("Skipping monitor check - processing in progress")
            return
        self.monitor_status.setText(f"Last checked: {datetime.now().strftime('%H:%M:%S')}")
    
    def generate_content_hub(self):
        """Start content hub generation in background thread"""
        if self.is_processing:
            QMessageBox.warning(self, "Processing", "Another operation is in progress. Please wait.")
            return
        
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "Please enter a valid URL.")
            return
        
        self.set_processing_state(True)
        
        # Create extraction worker with content manager
        worker = ExtractionWorker(url, self.config, self.content_manager)
        worker.progress.connect(self.on_progress_update)
        worker.finished.connect(self.on_extraction_finished)
        worker.error.connect(self.on_worker_error)
        
        self.workers.append(worker)
        worker.start()
    
    def export_all_formats(self):
        """Export all file formats in background"""
        if self.is_processing:
            QMessageBox.warning(self, "Processing", "Another operation is in progress.")
            return
        
        # Get current data from content manager
        data = self.content_manager.get_data_for_html()
        if not data.get("total_items", 0):
            QMessageBox.information(self, "No Data", "No content to export. Generate content first.")
            return
        
        self.set_processing_state(True)
        
        metadata = {
            "updated": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "source": self.url_input.text()
        }
        
        # Create workers for each format, passing output_dir
        for fmt in ["html", "json", "csv"]:
            worker = FileSaveWorker(fmt, data, metadata, self.output_dir)
            worker.finished.connect(lambda f, fmt=fmt: logger.info(f"{fmt.upper()} saved: {f}"))
            worker.error.connect(lambda e, fmt=fmt: logger.error(f"{fmt.upper()} error: {e}"))
            worker.finished.connect(self.on_export_finished)
            self.workers.append(worker)
            worker.start()
    
    def on_export_finished(self, filename: str):
        """Handle export completion"""
        # When any export finishes, check if all are done
        if all(not w.isRunning() for w in self.workers if isinstance(w, FileSaveWorker)):
            self.set_processing_state(False)
            QMessageBox.information(self, "Export Complete", "All files exported successfully.")
    
    def view_content_library(self):
        """View content library with thread-safe file access"""
        try:
            json_path = os.path.join(self.output_dir, "liberty-content-library.json")
            content = safe_file_read(json_path)
            if content:
                dialog = QDialog(self)
                dialog.setWindowTitle("Content Library")
                dialog.resize(800, 600)
                
                text_edit = QLineEdit()
                text_edit.setReadOnly(True)
                text_edit.setText(content[:2000] + ("..." if len(content) > 2000 else ""))
                
                layout = QVBoxLayout()
                layout.addWidget(text_edit)
                dialog.setLayout(layout)
                dialog.exec()
            else:
                QMessageBox.information(self, "No Data", "Content library not found. Generate it first.")
        except Exception as e:
            logger.error(f"Error viewing library: {traceback.format_exc()}")
            QMessageBox.critical(self, "Error", f"Failed to view library: {str(e)}")
    
    def stop_processing(self):
        """Stop all background processing gracefully"""
        for worker in self.workers:
            if worker.isRunning():
                worker.stop()
        self.workers.clear()
        self.set_processing_state(False)
        self.status_bar.showMessage("Processing stopped")
    
    def set_processing_state(self, processing: bool):
        """Update UI for processing state"""
        self.is_processing = processing
        self.btn_generate.setEnabled(not processing)
        self.btn_export.setEnabled(not processing)
        self.btn_view.setEnabled(not processing)
        self.btn_stop.setEnabled(processing)
        self.progress_bar.setVisible(processing)
        
        if processing:
            self.status_bar.showMessage("Processing...")
        else:
            self.progress_bar.setValue(0)
            self.status_bar.showMessage("Ready")
    
    def on_progress_update(self, value: int, message: str):
        """Handle progress updates from workers"""
        self.progress_bar.setValue(value)
        self.status_bar.showMessage(message)
        logger.info(f"Progress: {value}% - {message}")
    
    def on_extraction_finished(self, raw_links: List[tuple], organized_data: Dict):
        """Handle successful extraction"""
        try:
            self.update_stats_from_manager()
            QMessageBox.information(
                self, 
                "Success", 
                f"Extracted {len(raw_links)} items into {len(organized_data.get('sections', {}))} sections."
            )
        except Exception as e:
            logger.error(f"Error processing extraction results: {traceback.format_exc()}")
            QMessageBox.critical(self, "Error", f"Failed to process results: {str(e)}")
        finally:
            self.set_processing_state(False)
    
    def on_worker_error(self, error_message: str):
        """Handle worker errors"""
        logger.error(f"Worker error: {error_message}")
        QMessageBox.critical(self, "Processing Error", error_message)
        self.set_processing_state(False)
    
    def update_stats_from_manager(self):
        """Update statistics from content manager"""
        try:
            data = self.content_manager.get_data_for_html()
            total_items = data.get('total_items', 0)
            section_count = len(data.get('sections', {}))
            tag_count = len(data.get('all_tags', []))
            
            self.lbl_items.setText(f"Items: {total_items}")
            self.lbl_sections.setText(f"Sections: {section_count}")
            self.lbl_tags.setText(f"Tags: {tag_count}")
            self.lbl_last_update.setText(f"Last: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            logger.error(f"Error updating stats: {traceback.format_exc()}")
    
    def closeEvent(self, event):
        """Handle application close with cleanup"""
        self.stop_processing()
        self.stats_timer.stop()
        self.monitor_timer.stop()
        event.accept()

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point with proper error handling and resource checks"""
    try:
        # Validate write permissions
        if not os.access(os.getcwd(), os.W_OK):
            error_msg = "Application directory is not writable. Please run from a different location."
            logger.critical(error_msg)
            print(f"ERROR: {error_msg}")
            sys.exit(1)
        
        # Create application
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setApplicationName("Liberty Express Content Hub")
        
        # Load stylesheet from file if exists, otherwise use default
        style_file = "style.qss"
        if os.path.exists(style_file):
            with open(style_file, 'r') as f:
                app.setStyleSheet(f.read())
        else:
            app.setStyleSheet("""
                QMainWindow { background-color: #0a001a; }
                QWidget { color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; }
                QPushButton {
                    background-color: #1a1a2e; border: 2px solid #00ffff; padding: 10px;
                    border-radius: 6px; font-weight: bold; min-width: 150px;
                }
                QPushButton:hover:!pressed { background-color: #2a2a3e; border-color: #00ffff; }
                QPushButton:pressed { background-color: #00ffff; color: #000000; }
                QPushButton:disabled { background-color: #0a0a1a; border-color: #555555; color: #888888; }
                QGroupBox {
                    border: 2px solid rgba(0, 255, 255, 0.3); border-radius: 8px;
                    margin-top: 15px; padding-top: 15px; font-size: 14px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin; left: 15px; padding: 0 10px 0 10px;
                    color: #00ffff; font-weight: bold;
                }
                QProgressBar {
                    border: 1px solid #00ffff; border-radius: 4px; text-align: center;
                    background-color: #1a1a2e; height: 20px;
                }
                QProgressBar::chunk { background-color: #00ffff; border-radius: 3px; }
                QStatusBar { background-color: #1a1a2e; color: #cccccc; font-size: 12px; }
            """)
        
        window = DashboardWindow()
        window.show()
        
        exit_code = app.exec()
        logger.info("Application shutdown complete")
        return exit_code
        
    except Exception as e:
        error_msg = f"Application crashed: {traceback.format_exc()}"
        logger.critical(error_msg)
        
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle("Fatal Error")
            msg_box.setText("The application encountered a fatal error and must close.")
            msg_box.setDetailedText(error_msg)
            msg_box.exec()
        except:
            print(f"FATAL ERROR: {error_msg}")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
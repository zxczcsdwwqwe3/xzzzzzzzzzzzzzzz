import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
import logging
import re
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SkyScraper:
    def __init__(self):
        self.base_url = "https://guidatv.org"
        self.start_url = "https://guidatv.org/canali"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.cache_lock = threading.Lock()
        self.desc_cache = {} 
        self.clean_regex = re.compile(
            r'\s+\d+\s+(min|ore).*|(?:\s*\|.*)|(?:\s+—.*)|(?:\s+Live\b\s*$)', 
            re.IGNORECASE
        )

        self.target_map = {
            "Digitale Terrestre": [
                {"u": "rai-1", "n": "Rai 1"},
                {"u": "rai-2", "n": "Rai 2"},
                {"u": "rai-3", "n": "Rai 3"},
                {"u": "rai-4", "n": "Rai 4"},
                {"u": "rai-5", "n": "Rai 5"},
                {"u": "rete-4", "n": "Rete 4"},
                {"u": "canale-5", "n": "Canale 5"},
                {"u": "italia-uno", "n": "Italia 1"},
                {"u": "la7", "n": "La7"},
                {"u": "tv8", "n": "TV8"},
                {"u": "nove", "n": "Nove"},
                {"u": "canale-20", "n": "20 Mediaset"},
                {"u": "real-time", "n": "Real Time"},
                {"u": "boing", "n": "Boing"},
                {"u": "k2", "n": "K2"},
                {"u": "rai-gulp", "n": "Rai Gulp"},
                {"u": "frisbee", "n": "Frisbee"},
                {"u": "dmax", "n": "DMAX"},
                {"u": "rai-sport", "n": "Rai Sport"},
                {"u": "sportitalia", "n": "Sportitalia"}
            ],
            "Sport": [
                {"u": "sky-sport-24", "n": "Sky Sport 24"},
                {"u": "sky-sport-uno", "n": "Sky Sport Uno"},
                {"u": "sky-sport-calcio", "n": "Sky Sport Calcio"},
                {"u": "sky-sport-tennis", "n": "Sky Sport Tennis"},
                {"u": "sky-sport-f1", "n": "Sky Sport F1"},
                {"u": "sky-sport-legend", "n": "Sky Sport Legend"},
                {"u": "sky-sport-motogp", "n": "Sky Sport MotoGP"},
                {"u": "sky-sport-basket", "n": "Sky Sport Basket"},
                {"u": "sky-sport-arena", "n": "Sky Sport Arena"},
                {"u": "sky-sport-max", "n": "Sky Sport Max"},
                {"u": "sky-sport-mix", "n": "Sky Sport Mix"},
                {"u": "sky-sport-golf", "n": "Sky Sport Golf"},
                {"u": "sky-sport-hd-1", "n": "Sky Sport 251"},
                {"u": "sky-sport-hd-2", "n": "Sky Sport 252"},
                {"u": "sky-sport-hd-3", "n": "Sky Sport 253"},
                {"u": "sky-sport-hd-4", "n": "Sky Sport 254"},
                {"u": "sky-sport-hd-5", "n": "Sky Sport 255"},
                {"u": "sky-sport-hd-6", "n": "Sky Sport 256"},
                {"u": "sky-sport-hd-7", "n": "Sky Sport 257"},
                {"u": "sky-sport-hd-8", "n": "Sky Sport 258"},
                {"u": "sky-sport-hd-9", "n": "Sky Sport 259"},
                {"u": "eurosport-1", "n": "Eurosport 1"},
                {"u": "eurosport-2", "n": "Eurosport 2"}
            ],
            "Cinema": [
                {"u": "sky-cinema-uno", "n": "Sky Cinema Uno"},
                {"u": "sky-cinema-uno-plus-24", "n": "Sky Cinema Uno +24"},
                {"u": "sky-cinema-collection", "n": "Sky Cinema Collection"},
                {"u": "sky-cinema-stories", "n": "Sky Cinema Stories"},
                {"u": "sky-cinema-family", "n": "Sky Cinema Family"},
                {"u": "sky-cinema-action", "n": "Sky Cinema Action"},
                {"u": "sky-cinema-suspense", "n": "Sky Cinema Suspense"},
                {"u": "sky-cinema-romance", "n": "Sky Cinema Romance"},
                {"u": "sky-cinema-drama", "n": "Sky Cinema Drama"},
                {"u": "sky-cinema-comedy", "n": "Sky Cinema Comedy"}
            ],
            "Intrattenimento": [
                {"u": "sky-uno", "n": "Sky Uno"},
                {"u": "sky-uno-plus-1", "n": "Sky Uno +1"},
                {"u": "sky-atlantic", "n": "Sky Atlantic"},
                {"u": "sky-atlantic-plus-1", "n": "Sky Atlantic +1"},
                {"u": "sky-serie", "n": "Sky Serie"},
                {"u": "sky-investigation", "n": "Sky Investigation"},
                {"u": "sky-crime", "n": "Sky Crime"},
                {"u": "sky-adventure", "n": "Sky Adventure"},
                {"u": "mtv", "n": "MTV"},
                {"u": "comedy-central", "n": "Comedy Central"}
            ],
            "Documentari": [
                {"u": "sky-arte", "n": "Sky Arte"},
                {"u": "sky-documentaries", "n": "Sky Documentaries"},
                {"u": "sky-nature", "n": "Sky Nature"},
                {"u": "discovery-channel", "n": "Discovery Channel"},
                {"u": "national-geographic", "n": "National Geographic"},
                {"u": "history-channel", "n": "History Channel"}
            ],
            "News": [
                {"u": "sky-tg24", "n": "Sky TG 24"},
                {"u": "sky-meteo-24", "n": "Sky Meteo 24"}
            ]
        }

    def _clean_title(self, title):
        """Rimuove durata, tag Live spuri e dettagli inutili dal titolo."""
        if not title:
            return "N/A"
        
        cleaned = self.clean_regex.split(title)[0]
        cleaned = cleaned.strip()
        
        if cleaned.lower().endswith(" live"):
            cleaned = cleaned[:-5].strip()
            
        return cleaned if cleaned else "Programma"

    def _clean_description(self, desc):
        """Rimuove i puntini di sospensione ('...' o '\u2026') ad inizio descrizione
        e ripulisce artefatti di encoding errato (spazi non-breaking, caratteri spuri)."""
        if not desc:
            return desc
        cleaned = desc.strip()
        cleaned = re.sub(r'^(?:\.{2,}|\u2026)+\s*', '', cleaned)
        cleaned = cleaned.replace('\xa0', ' ')
        cleaned = re.sub(r'[\x80-\x9f\ufffd]', '', cleaned)
        cleaned = re.sub(r' {2,}', ' ', cleaned)
        return cleaned.strip()

    def get_matched_channels(self):
        """Trova gli URL reali sul sito guidatv.org basandosi sulla mappa target."""
        try:
            res = self.session.get(self.start_url, timeout=15)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            all_links = [l for l in soup.find_all('a', href=True) if l['href'].startswith('/canali/')]
            
            matched = []
            for cat, ch_list in self.target_map.items():
                for target in ch_list:
                    target_id = target['u'].replace('-', '').lower()
                    found = False
                    
                    for link in all_links:
                        href = link['href']
                        slug = href.split('/')[-1].replace('-', '').lower()
                        
                        if target_id in slug or slug in target_id:
                            matched.append({
                                "nome": target['n'],
                                "url": self.base_url + href,
                                "categoria": cat
                            })
                            found = True
                            break
                    
                    if not found and target['u'] == "sky-adventure":
                        for link in all_links:
                            if "adventure" in link['href'].lower():
                                matched.append({
                                    "nome": target['n'],
                                    "url": self.base_url + link['href'],
                                    "categoria": cat
                                })
                                break
            return matched
        except Exception as e:
            logger.error(f"Errore nel recupero canali: {e}")
            return []

    def _get_full_description(self, detail_url):
        """Scarica e restituisce la descrizione completa da una pagina di dettaglio (con cache)."""
        if not detail_url:
            return ""
            
        with self.cache_lock:
            if detail_url in self.desc_cache:
                return self.desc_cache[detail_url]

        full_url = self.base_url + detail_url if detail_url.startswith('/') else detail_url
        try:
            res = self.session.get(full_url, timeout=5)
            if res.status_code == 200:
                res.encoding = 'utf-8'  
                soup = BeautifulSoup(res.text, 'html.parser')
                
                script = soup.find('script', id='__NEXT_DATA__')
                if script:
                    try:
                        data = json.loads(script.string)
                        props = data.get('props', {}).get('pageProps', {})

                        prog_obj = props.get('program') or props.get('initialData', {}).get('program', {})
                        desc = prog_obj.get('description') or prog_obj.get('descrizione') or prog_obj.get('plot')
                        if desc:
                            desc_clean = desc.strip()
                            with self.cache_lock:
                                self.desc_cache[detail_url] = desc_clean
                            return desc_clean
                    except Exception:
                        pass
                
                meta_desc = soup.find('meta', property='og:description') or soup.find('meta', name='description')
                if meta_desc and meta_desc.get('content'):
                    desc_clean = meta_desc['content'].strip()
                    with self.cache_lock:
                        self.desc_cache[detail_url] = desc_clean
                    return desc_clean
        except Exception as e:
            logger.debug(f"Impossibile scaricare descrizione completa per {detail_url}: {e}")
            
        return ""

    def _extract_programs(self, soup):
        """Estrae i dati dei programmi preferendo il flusso Next.js App Router (RSC)."""
        from datetime import timezone
        from zoneinfo import ZoneInfo
        
        try:
            scripts = soup.find_all('script')
            all_text = ""
            for s in scripts:
                if s.string and 'self.__next_f.push' in s.string:
                    all_text += s.string
            
            if all_text:

                raw_strings = []
                for m in re.finditer(r'self\.__next_f\.push\(\[\d+,\s*"(.*?)"\]\)', all_text, re.DOTALL):
                    s_val = m.group(1)
                    s_val = s_val.replace('\\\\', '\\').replace('\\n', '\n').replace('\\/', '/')
                    raw_strings.append(s_val)
                
                combined_text = "".join(raw_strings)
                
                program_pattern = re.compile(
                    r'\\*"\s*id\s*\\*"\s*:\s*\\*"\s*(?P<id>[a-zA-Z0-9_\-]+)\s*\\*"\s*,\s*'
                    r'\\*"\s*title\s*\\*"\s*:\s*\\*"\s*(?P<title>.*?)\s*\\*"\s*,\s*'
                    r'\\*"\s*description\s*\\*"\s*:\s*\\*"\s*(?P<desc>.*?)\s*\\*"\s*,\s*.*?'
                    r'\\*"\s*inizio\s*\\*"\s*:\s*\\*"\s*(?P<inizio>.*?)\s*\\*"\s*,\s*'
                    r'\\*"\s*fine\s*\\*"\s*:\s*\\*"\s*(?P<fine>.*?)\s*\\*"',
                    re.DOTALL
                )
                
                raw_programs = []
                rome_tz = ZoneInfo("Europe/Rome")
                
                for m in program_pattern.finditer(combined_text):
                    title_raw = m.group('title')
                    desc_raw = m.group('desc')
                    inizio_raw = m.group('inizio')
                    fine_raw = m.group('fine')
                    
                    def clean_escapes(s):
                        s = re.sub(r'\\+"', '"', s)
                        s = re.sub(r"\\+'", "'", s)
                        s = re.sub(
                            r'\\u([0-9a-fA-F]{4})',
                            lambda m: chr(int(m.group(1), 16)),
                            s
                        )
                        # Sostituisce le sequenze di escape comuni
                        s = s.replace('\\n', ' ').replace('\\t', ' ').replace('\\r', '').replace('\\\\', '\\')
                        return s
                            
                    title = clean_escapes(title_raw)
                    desc = clean_escapes(desc_raw)
                    inizio = clean_escapes(inizio_raw)
                    fine = clean_escapes(fine_raw)
                    
                    try:
                        inizio_dt = datetime.fromisoformat(inizio.replace('Z', '+00:00'))
                        fine_dt = datetime.fromisoformat(fine.replace('Z', '+00:00'))
                    except Exception:
                        continue
                        
                    raw_programs.append({
                        "inizio_dt": inizio_dt,
                        "fine_dt": fine_dt,
                        "title": title,
                        "desc": desc
                    })
                
                if raw_programs:

                    now_utc = datetime.now(timezone.utc)
                    current_index = -1
                    for i, p in enumerate(raw_programs):
                        if p['inizio_dt'] <= now_utc < p['fine_dt']:
                            current_index = i
                            break
                    
                    if current_index == -1:
                        for i, p in enumerate(raw_programs):
                            if p['inizio_dt'] >= now_utc:
                                current_index = i
                                break
                    
                    if current_index == -1:
                        current_index = 0
                        
                    selected_programs = raw_programs[current_index:]
                    
                    extracted = []
                    for p in selected_programs:
                        local_start = p['inizio_dt'].astimezone(rome_tz).strftime("%H:%M")
                        extracted.append({
                            "ora": local_start,
                            "titolo": self._clean_title(p['title']),
                            "descrizione": self._clean_description(p['desc'].strip())
                        })
                        
                    if extracted:
                        return extracted
        except Exception as e:
            logger.debug(f"Errore nel parsing del flusso Next.js RSC: {e}")

        script = soup.find('script', id='__NEXT_DATA__')
        if script:
            try:
                data = json.loads(script.string)
                props = data.get('props', {}).get('pageProps', {})
                programs_list = (props.get('initialData', {}).get('channel', {}).get('programs', []) or 
                                 props.get('programs', []) or [])
                
                extracted = []
                for p in programs_list:
                    ora = p.get('startTime') or p.get('ora') or ""
                    if 'T' in str(ora):
                        ora = ora.split('T')[1][:5]
                    else:
                        ora = str(ora)[:5]
                    
                    titolo_raw = p.get('title') or p.get('titolo') or "N/A"
                    desc_raw = (p.get('description') or p.get('descrizione') or p.get('desc') or "").strip()
                    
                    detail_url = p.get('link') or p.get('url') or p.get('href')
                    if not detail_url and p.get('slug'):
                        detail_url = f"/programma/{p.get('slug')}"
                    
                    if (not desc_raw or desc_raw.endswith('...') or desc_raw.endswith('…')) and detail_url:
                        full_desc = self._get_full_description(detail_url)
                        if full_desc:
                            desc_raw = full_desc
                    
                    if ora and titolo_raw:
                        extracted.append({
                            "ora": ora, 
                            "titolo": self._clean_title(titolo_raw),
                            "descrizione": self._clean_description(desc_raw)
                        })
                if extracted:
                    return extracted
            except Exception as e:
                logger.debug(f"Errore nel parsing del JSON __NEXT_DATA__: {e}")

        extracted = []
        items = soup.find_all(['div', 'li'], class_=True)
        for item in items:
            text = item.get_text(" ", strip=True)
            if len(text) > 5 and ":" in text[:6]:
                parts = text.split(" ", 1)
                ora_raw = parts[0].strip()
                ora = ora_raw.rstrip('.')
                
                if len(ora) == 5 and ora[2] == ":":
                    raw_title_desc = parts[1].strip() if len(parts) > 1 else "Programma"
                    titolo_raw = raw_title_desc
                    descrizione = ""
                    
                    link_tag = item.find('a', href=True) or (item if item.name == 'a' and item.has_attr('href') else None)
                    detail_url = link_tag['href'] if link_tag else None
                    
                    desc_tag = item.find(lambda tag: tag.name in ['p', 'span', 'div'] and 
                                         any('desc' in str(cls).lower() or 'plot' in str(cls).lower() 
                                             for cls in tag.get('class', [])))
                    if desc_tag:
                        descrizione = desc_tag.get_text(" ", strip=True)
                        titolo_raw = titolo_raw.replace(descrizione, "").strip()
                    
                    if "|" in titolo_raw:
                        left_side, right_side = titolo_raw.split("|", 1)
                        titolo_raw = left_side.strip()
                        if not descrizione:
                            category_and_desc = right_side.split(".", 1)
                            if len(category_and_desc) > 1:
                                descrizione = category_and_desc[1].strip()
                                
                    if (not descrizione or descrizione.endswith('...') or descrizione.endswith('…')) and detail_url:
                        full_desc = self._get_full_description(detail_url)
                        if full_desc:
                            descrizione = full_desc
                    
                    extracted.append({
                        "ora": ora, 
                        "titolo": self._clean_title(titolo_raw),
                        "descrizione": self._clean_description(descrizione.strip())
                    })
        return extracted

    def scrape_channel(self, ch):
        """Scarica e processa un singolo canale."""
        try:
            res = self.session.get(ch['url'], timeout=10)
            res.raise_for_status()
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            programs = self._extract_programs(soup)
            
            seen = set()
            unique_progs = []
            for p in programs:
                key = f"{p['ora']}-{p['titolo']}"
                if key not in seen:
                    unique_progs.append(p)
                    seen.add(key)

            return {
                "canale": ch['nome'],
                "categoria": ch['categoria'],
                "programmi": unique_progs[:12],
                "aggiornato": datetime.now().strftime("%H:%M")
            }
        except Exception as e:
            logger.debug(f"Errore nello scraping del canale {ch['nome']}: {e}")
            return None

    def run(self):
        start_time = time.time()
        channels = self.get_matched_channels()
        
        if not channels:
            logger.warning("Nessun canale trovato. Verifica la connessione o l'URL.")
            return

        logger.info(f"Trovati {len(channels)} canali da scansionare...")

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.scrape_channel, channels))
            
        final_data = [r for r in results if r is not None]
        
        with open('guida_tv_sky.json', 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        duration = round(time.time() - start_time, 1)
        logger.info(f"Fatto! {len(final_data)} canali salvati in {duration}s. Caching descrizioni attivo.")

if __name__ == "__main__":
    scraper = SkyScraper()
    scraper.run()
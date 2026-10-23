import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
import re
from urllib.parse import unquote

class MarkdownConverter(HTMLParser):
    def __init__(self, media_rel_dir="media"):
        super().__init__()
        self.output = []
        self.ignore = False
        self.media_rel_dir = media_rel_dir
        self.list_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in ('script', 'style'):
            self.ignore = True
            return
        
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            level = int(tag[1])
            self.output.append(f"\n\n{'#' * level} ")
        elif tag == 'p':
            self.output.append("\n\n")
        elif tag == 'br':
            self.output.append("\n")
        elif tag in ('b', 'strong'):
            self.output.append("**")
        elif tag in ('i', 'em'):
            self.output.append("*")
        elif tag in ('ul', 'ol'):
            self.list_depth += 1
            self.output.append("\n")
        elif tag == 'li':
            indent = "  " * (self.list_depth - 1)
            self.output.append(f"\n{indent}- ")
        elif tag == 'blockquote':
            self.output.append("\n\n> ")
        elif tag == 'img':
            src = attrs_dict.get('src', '')
            if src:
                nome_img = os.path.basename(unquote(src))
                alt = attrs_dict.get('alt', nome_img)
                self.output.append(f"\n\n![{alt}]({self.media_rel_dir}/{nome_img})\n\n")

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.ignore = False
        elif tag in ('b', 'strong'):
            self.output.append("**")
        elif tag in ('i', 'em'):
            self.output.append("*")
        elif tag in ('ul', 'ol'):
            self.list_depth = max(0, self.list_depth - 1)
            self.output.append("\n")
        elif tag in ('p', 'blockquote'):
            self.output.append("\n")

    def handle_data(self, data):
        if not self.ignore:
            self.output.append(data)

    def get_text(self):
        raw = "".join(self.output)
        raw = re.sub(r'[ \t]+', ' ', raw)
        raw = re.sub(r'\n[ \t]+', '\n', raw)
        raw = re.sub(r'\n{3,}', '\n\n', raw)
        return raw.strip()


def sanifica_nome(nome):
    nome_pulito = re.sub(r'[\\/*?:"<>|]', "", nome)
    nome_pulito = re.sub(r'\s+', ' ', nome_pulito)
    return nome_pulito[:60].strip()


def converti_epub(epub_path):
    print(f"--> [1/6] Cerco il file: {epub_path}")
    if not os.path.isfile(epub_path):
        print(f"[!] ERRORE: File '{epub_path}' non trovato nella directory corrente!")
        print(f"    File presenti: {os.listdir('.')}")
        return

    nome_base = os.path.splitext(os.path.basename(epub_path))[0]
    out_dir = os.path.join(".", sanifica_nome(nome_base))
    media_dir = os.path.join(out_dir, "media")
    os.makedirs(media_dir, exist_ok=True)

    print(f"--> [2/6] Apertura archivio ZIP...")
    try:
        with zipfile.ZipFile(epub_path, 'r') as z:
            namelist = z.namelist()
            print(f"    Trovati {len(namelist)} elementi interni all'EPUB.")
            
            # Trova file OPF
            opf_rel_path = None
            if "META-INF/container.xml" in namelist:
                container_data = z.read("META-INF/container.xml")
                root = ET.fromstring(container_data)
                for elem in root.iter():
                    if elem.tag.endswith('rootfile'):
                        opf_rel_path = elem.attrib.get('full-path')
                        break
            
            # Fallback se container.xml non trova il path
            if not opf_rel_path:
                for name in namelist:
                    if name.endswith('.opf'):
                        opf_rel_path = name
                        break

            if not opf_rel_path:
                print("[!] ERRORE: Nessun descrittore .opf trovato nell'EPUB.")
                return

            print(f"--> [3/6] Descrittore trovato: {opf_rel_path}")
            opf_dir = os.path.dirname(opf_rel_path)
            opf_data = z.read(opf_rel_path)
            opf_root = ET.fromstring(opf_data)

            # Mappa manifest senza dipendere da namespace rigidi
            manifest = {}
            for elem in opf_root.iter():
                if elem.tag.endswith('item') and 'id' in elem.attrib and 'href' in elem.attrib:
                    manifest[elem.attrib['id']] = elem.attrib['href']

            # Leggi ordine spine
            spine_items = []
            for elem in opf_root.iter():
                if elem.tag.endswith('itemref') and 'idref' in elem.attrib:
                    idref = elem.attrib['idref']
                    if idref in manifest:
                        href = unquote(manifest[idref])
                        full_href = os.path.normpath(os.path.join(opf_dir, href)).replace('\\', '/')
                        spine_items.append(full_href)

            # Fallback: se la spine è vuota, prendi tutti i file html/xhtml in ordine alfabetico
            if not spine_items:
                print("    Attenzione: spine non mappata, uso fallback su file HTML/XHTML.")
                spine_items = sorted([f for f in namelist if f.endswith(('.xhtml', '.html', '.htm'))])

            print(f"--> [4/6] Sezioni da elaborare: {len(spine_items)}")

            # Estrai immagini
            estensioni_img = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')
            for nome_nel_zip in namelist:
                if nome_nel_zip.lower().endswith(estensioni_img):
                    file_dest = os.path.join(media_dir, os.path.basename(nome_nel_zip))
                    with open(file_dest, 'wb') as img_out:
                        img_out.write(z.read(nome_nel_zip))

            # Elaborazione capitoli
            capitoli = []
            for idx, entry_path in enumerate(spine_items):
                try:
                    html_bytes = z.read(entry_path)
                except KeyError:
                    # prova a cercare ignorando case sensitive o percorsi relativi
                    match = [n for n in namelist if n.lower() == entry_path.lower() or os.path.basename(n) == os.path.basename(entry_path)]
                    if match:
                        html_bytes = z.read(match[0])
                    else:
                        continue

                try:
                    html_str = html_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    html_str = html_bytes.decode('latin-1', errors='ignore')

                parser = MarkdownConverter(media_rel_dir="media")
                parser.feed(html_str)
                md_text = parser.get_text()

                if len(md_text.strip()) < 20:
                    continue

                # Estrazione titolo
                match_titolo = re.search(r'^#+\s+(.+)$', md_text, re.MULTILINE)
                if match_titolo:
                    titolo = match_titolo.group(1).strip()
                else:
                    linee = [l.strip() for l in md_text.splitlines() if l.strip()]
                    titolo = linee[0][:40].strip() if linee else f"Capitolo {idx+1}"

                titolo_sanificato = sanifica_nome(titolo)
                nome_file = f"{len(capitoli)+1:02d} - {titolo_sanificato}.md"
                capitoli.append({
                    'file_name': nome_file,
                    'titolo': titolo,
                    'contenuto': md_text
                })

            if not capitoli:
                print("[!] ERRORE: Nessun testo estratto. Il libro potrebbe essere protetto da DRM o composto solo da immagini.")
                return

            print(f"--> [5/6] Scrittura di {len(capitoli)} capitoli...")
            total = len(capitoli)
            for i, cap in enumerate(capitoli):
                if i > 0:
                    prev_name = capitoli[i-1]['file_name'][:-3]
                    prev_link = f"[[{prev_name}|← Precedente]]"
                else:
                    prev_link = "← Inizio"

                if i < total - 1:
                    next_name = capitoli[i+1]['file_name'][:-3]
                    next_link = f"[[{next_name}|Successivo →]]"
                else:
                    next_link = "Fine →"

                nav_header = f"{prev_link} | [[00 - Indice|Indice]] | {next_link}\n\n---\n\n"
                nav_footer = f"\n\n---\n\n{prev_link} | [[00 - Indice|Indice]] | {next_link}\n"

                file_path = os.path.join(out_dir, cap['file_name'])
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(nav_header + cap['contenuto'] + nav_footer)

            # Scrittura Indice MOC
            print("--> [6/6] Creazione 00 - Indice.md...")
            indice_path = os.path.join(out_dir, "00 - Indice.md")
            with open(indice_path, 'w', encoding='utf-8') as f:
                f.write("---\n")
                f.write(f"titolo: \"{nome_base}\"\n")
                f.write("tags:\n  - tipo/libro\n  - stato/da-leggere\n")
                f.write("---\n\n")
                f.write(f"# {nome_base}\n\n## Indice dei Capitoli\n\n")
                for cap in capitoli:
                    nome_nota = cap['file_name'][:-3]
                    f.write(f"- [[{nome_nota}|{cap['titolo']}]]\n")

            print(f"\n[OK] Fatto! Cartella creata: {os.path.abspath(out_dir)}")

    except Exception as e:
        print(f"[!] ECCEZIONE durante l'elaborazione: {e}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "epitteto.epub"
    converti_epub(target)
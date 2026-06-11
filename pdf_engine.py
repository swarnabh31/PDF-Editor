import fitz  # PyZYMuPDF
import os
import tempfile
import platform
from PySide6.QtCore import Qt


class PDFOverlayEngine:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.overlays = {}  # {page_num: [overlay_dict, ...]}
        self.custom_fonts = {}

    def get_page_count(self):
        return len(self.doc)

    def render_page_to_pixmap(self, page_num, zoom=2.0):
        page = self.doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        return page.get_pixmap(matrix=mat)

    def delete_page(self, page_num):
        if page_num < 0 or page_num >= len(self.doc):
            return
        self.doc.delete_page(page_num)
        new_overlays = {}
        for p, data in self.overlays.items():
            if p < page_num:
                new_overlays[p] = data
            elif p > page_num:
                new_overlays[p - 1] = data
        self.overlays = new_overlays

    def insert_blank_page(self, page_num):
        insert_idx = page_num + 1
        self.doc.new_page(pno=insert_idx, width=595, height=842)
        new_overlays = {}
        for p, data in self.overlays.items():
            if p <= page_num:
                new_overlays[p] = data
            else:
                new_overlays[p + 1] = data
        self.overlays = new_overlays
        return insert_idx

    def append_pdf(self, source_path):
        src_doc = fitz.open(source_path)
        self.doc.insert_pdf(src_doc)
        src_doc.close()

    def extract_font_in_rect(self, page_num, pdf_rect):
        page = self.doc[page_num]
        text_dict = page.get_text("dict", clip=pdf_rect)
        font_name = None
        font_size = None

        for block in text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", " ").strip():
                        font_name = span.get("font")
                        font_size = span.get("size")
                        break
                if font_name: break
            if font_name: break

        if not font_name: return None, None

        lower = font_name.lower().replace("-", " ").replace("  ", " ")
        clean = font_name.split("+", 1)[1] if "+" in font_name else font_name

        builtin_aliases = {
            "helvetica": "helv", "helv": "helv", "arial": "helv",
            "timesnewroman": "tiro", "times": "tiro", "tiro": "tiro",
            "courier": "cour", "couriernew": "cour", "cour": "cour",
        }
        for alias, ref in builtin_aliases.items():
            if alias in lower: return ref, font_size

        xref = None
        for f in page.get_fonts(full=True):
            if f[3] == font_name or f[4] == font_name:
                xref = f[0]
                break

        if xref:
            try:
                font_info = self.doc.extract_font(xref)
                buf = font_info[2] if len(font_info) > 2 else None
                ext = font_info[0] if font_info[0] else "ttf"
                if buf:
                    temp_path = os.path.join(tempfile.gettempdir(), f"pdf_extracted_{xref}.{ext}")
                    if not os.path.exists(temp_path):
                        with open(temp_path, "wb") as fh: fh.write(buf)
                    ref_name = f"F{xref}"
                    self.custom_fonts[clean] = {"temp_path": temp_path, "ref_name": ref_name}
                    return clean, font_size
            except Exception as e:
                print(f"[PDFEngine] Font extraction error: {e}")

        return clean, font_size

    def add_overlay(self, page_num, overlay_data):
        self.overlays.setdefault(page_num, []).append(overlay_data)

    def remove_overlay(self, page_num, overlay_id):
        if page_num in self.overlays:
            self.overlays[page_num] = [o for o in self.overlays[page_num] if o["id"] != overlay_id]

    def update_overlay(self, page_num, overlay_id, new_data):
        for o in self.overlays.get(page_num, []):
            if o["id"] == overlay_id:
                o.update(new_data)
                break

    def get_overlays_for_page(self, page_num):
        return self.overlays.get(page_num, [])

    def save(self, output_path, zoom=2.0):
        scale = 1.0 / zoom
        for page_num, overlays in self.overlays.items():
            if not overlays: continue
            page = self.doc[page_num]
            registered_fonts = {}

            for o in overlays:
                x0 = o["x"] * scale
                y0 = o["y"] * scale
                x1 = (o["x"] + o["width"]) * scale
                y1 = (o["y"] + o["height"]) * scale
                rect = fitz.Rect(x0, y0, x1, y1)
                if rect.is_empty or rect.is_infinite or x1 <= x0 or y1 <= y0: continue

                if o.get("image_path"):
                    try:
                        page.insert_image(rect, filename=o["image_path"])
                    except Exception as e:
                        print(f"[PDFEngine] Image insert error: {e}")
                    continue

                text = o.get("text", "").strip()
                if not text: continue

                bg = o.get("bg_color", "transparent")
                if bg and bg != "transparent":
                    br, bg_g, bb = self._hex_to_rgb(bg)
                    page.draw_rect(rect, color=(br, bg_g, bb), fill=(br, bg_g, bb))

                # --- EXTRACT STYLE FLAGS ---
                font_name = o.get("font_name", "helv")
                is_bold = o.get("font_bold", False)
                is_italic = o.get("font_italic", False)
                is_underline = o.get("font_underline", False)

                fontref = self._resolve_fontref(font_name, page, registered_fonts, is_bold, is_italic)
                tr, tg, tb = self._hex_to_rgb(o.get("text_color", "#000000"))
                font_size = max(4, int(o.get("font_size", 12)))

                align_flag = o.get("text_alignment", int(Qt.AlignmentFlag.AlignLeft))
                if align_flag == int(Qt.AlignmentFlag.AlignCenter):
                    pdf_align = fitz.TEXT_ALIGN_CENTER
                elif align_flag == int(Qt.AlignmentFlag.AlignRight):
                    pdf_align = fitz.TEXT_ALIGN_RIGHT
                else:
                    pdf_align = fitz.TEXT_ALIGN_LEFT

                result = page.insert_textbox(rect, text, fontname=fontref, fontsize=font_size, color=(tr, tg, tb),
                                             align=pdf_align)

                if result < 0:
                    page.insert_text(fitz.Point(x0 + 1, y0 + font_size), text, fontname=fontref, fontsize=font_size,
                                     color=(tr, tg, tb))
                    if is_underline:
                        est_width = len(text) * font_size * 0.6
                        ul_y = y0 + (font_size * 0.85)
                        page.draw_line(fitz.Point(x0, ul_y), fitz.Point(x0 + est_width, ul_y), color=(tr, tg, tb),
                                       width=max(1.0, font_size * 0.08))
                else:
                    if is_underline:
                        avg_char_width = font_size * 0.6
                        estimated_text_width = len(text) * avg_char_width

                        if pdf_align == fitz.TEXT_ALIGN_CENTER:
                            line_x0 = x0 + (rect.width - estimated_text_width) / 2
                            line_x1 = line_x0 + estimated_text_width
                        elif pdf_align == fitz.TEXT_ALIGN_RIGHT:
                            line_x1 = x1
                            line_x0 = x1 - estimated_text_width
                        else:
                            line_x0 = x0
                            line_x1 = x0 + estimated_text_width

                        line_x0 = max(x0, line_x0)
                        line_x1 = min(x1, line_x1)
                        ul_y = y0 + (font_size * 0.85)
                        line_width = max(1.0, font_size * 0.08)

                        page.draw_line(fitz.Point(line_x0, ul_y), fitz.Point(line_x1, ul_y), color=(tr, tg, tb),
                                       width=line_width)

        self.doc.save(output_path, garbage=4, deflate=True)

    def _resolve_fontref(self, font_name, page, registered, is_bold=False, is_italic=False):
        style_suffix = ""
        if is_bold and is_italic:
            style_suffix = "bi"
        elif is_bold:
            style_suffix = "b"
        elif is_italic:
            style_suffix = "i"

        cache_key = f"{font_name}_{style_suffix}"
        if cache_key in registered:
            return registered[cache_key]

        builtin_map = {
            "helv": "helv", "helvetica": "helv", "arial": "helv",
            "tiro": "tiro", "times": "tiro", "timesnewroman": "tiro",
            "cour": "cour", "courier": "cour", "couriernew": "cour"
        }
        lower_name = font_name.lower().replace(" ", "").replace("-", "")
        base_ref = builtin_map.get(lower_name, "helv")

        pymupdf_styled = {
            # PyMuPDF Base-14 short names: hebo=Helvetica-Bold, heit=Helvetica-Oblique, hebi=Helvetica-BoldOblique
            "helv": {"": "helv", "b": "hebo", "i": "heit", "bi": "hebi"},
            "tiro": {"": "tiro", "b": "tibo", "i": "tiit", "bi": "tibi"},
            "cour": {"": "cour", "b": "cobo", "i": "coit", "bi": "cozi"},
        }

        if base_ref in pymupdf_styled and style_suffix in pymupdf_styled[base_ref]:
            ref = pymupdf_styled[base_ref][style_suffix]
            registered[cache_key] = ref
            return ref

        if font_name in self.custom_fonts:
            base_info = self.custom_fonts[font_name]
            base_path = base_info["temp_path"]
            dir_name = os.path.dirname(base_path)
            file_name = os.path.basename(base_path)
            name_without_ext, ext = os.path.splitext(file_name)

            styled_name = name_without_ext
            if is_bold and is_italic:
                styled_name += " Bold Italic"
            elif is_bold:
                styled_name += " Bold"
            elif is_italic:
                styled_name += " Italic"

            styled_path = os.path.join(dir_name, styled_name + ext)
            if not os.path.exists(styled_path):
                styled_path = self._find_system_font(font_name, is_bold, is_italic)

            if styled_path and os.path.exists(styled_path):
                ref = f"F_{cache_key}"
                try:
                    page.insert_font(fontname=ref, fontfile=styled_path)
                    registered[cache_key] = ref
                    return ref
                except Exception as e:
                    print(f"[PDFEngine] Failed to load styled font {styled_path}: {e}")

        system_font_path = self._find_system_font(font_name, is_bold, is_italic)
        if system_font_path and os.path.exists(system_font_path):
            ref = f"F_sys_{cache_key}"
            try:
                page.insert_font(fontname=ref, fontfile=system_font_path)
                registered[cache_key] = ref
                return ref
            except Exception as e:
                print(f"[PDFEngine] Failed to load system font {system_font_path}: {e}")

        print(f"[PDFEngine] Warning: Styled variant for '{font_name}' not found. Falling back to base font.")
        registered[cache_key] = base_ref
        return base_ref

    def _find_system_font(self, family, is_bold, is_italic):
        system = platform.system()
        family_clean = family.replace(" ", "").lower()
        suffix = ""
        if is_bold and is_italic:
            suffix = " Bold Italic"
        elif is_bold:
            suffix = " Bold"
        elif is_italic:
            suffix = " Italic"
        extensions = [".ttf", ".otf", ".ttc"]

        if system == "Windows":
            font_dir = os.environ.get("WINDIR", "C:\\Windows") + "\\Fonts\\"
            for ext in extensions:
                path = os.path.join(font_dir, f"{family}{suffix}{ext}")
                if os.path.exists(path): return path
                if is_bold and not is_italic:
                    path = os.path.join(font_dir, f"{family_clean}bd{ext}")
                    if os.path.exists(path): return path
                elif is_italic and not is_bold:
                    path = os.path.join(font_dir, f"{family_clean}i{ext}")
                    if os.path.exists(path): return path
                elif is_bold and is_italic:
                    path = os.path.join(font_dir, f"{family_clean}bi{ext}")
                    if os.path.exists(path): return path
        elif system == "Darwin":
            font_dirs = ["/System/Library/Fonts/", "/Library/Fonts/", os.path.expanduser("~/Library/Fonts/")]
            for fd in font_dirs:
                for ext in extensions:
                    path = os.path.join(fd, f"{family}{suffix}{ext}")
                    if os.path.exists(path): return path
        elif system == "Linux":
            font_dirs = ["/usr/share/fonts/", "/usr/local/share/fonts/", os.path.expanduser("~/.fonts/")]
            for fd in font_dirs:
                fd = os.path.expanduser(fd)
                if os.path.exists(fd):
                    for root, dirs, files in os.walk(fd):
                        for f in files:
                            if f.lower().endswith(tuple(extensions)) and family_clean in f.lower():
                                if (is_bold and "bold" in f.lower()) or (is_italic and "italic" in f.lower()) or (
                                        not is_bold and not is_italic):
                                    return os.path.join(root, f)
        return None

    def _hex_to_rgb(self, hex_color):
        if not hex_color or hex_color == "transparent": return (1.0, 1.0, 1.0)
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3: hex_color = "".join(c * 2 for c in hex_color)
        return (int(hex_color[0:2], 16) / 255.0, int(hex_color[2:4], 16) / 255.0, int(hex_color[4:6], 16) / 255.0)
import fitz  # PyMuPDF
import os
import tempfile


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

    # ------------------------------------------------------------------
    # Page Management
    # ------------------------------------------------------------------
    def delete_page(self, page_num):
        """Deletes a page and shifts overlays to keep them aligned."""
        if page_num < 0 or page_num >= len(self.doc):
            return
        self.doc.delete_page(page_num)

        # Shift overlays
        new_overlays = {}
        for p, data in self.overlays.items():
            if p < page_num:
                new_overlays[p] = data
            elif p > page_num:
                new_overlays[p - 1] = data
            # If p == page_num, we discard the overlays for the deleted page
        self.overlays = new_overlays

    def insert_blank_page(self, page_num):
        """Inserts a blank A4 page AFTER the specified page_num."""
        insert_idx = page_num + 1
        self.doc.new_page(pno=insert_idx, width=595, height=842)

        # Shift overlays
        new_overlays = {}
        for p, data in self.overlays.items():
            if p <= page_num:
                new_overlays[p] = data
            else:
                new_overlays[p + 1] = data
        self.overlays = new_overlays
        return insert_idx

    def append_pdf(self, source_path):
        """Appends all pages from another PDF to the end of this document."""
        src_doc = fitz.open(source_path)
        self.doc.insert_pdf(src_doc)
        src_doc.close()
        # No overlay shifting needed, existing pages keep their indices.

    # ------------------------------------------------------------------
    # Font Picker
    # ------------------------------------------------------------------
    def extract_font_in_rect(self, page_num, pdf_rect):
        page = self.doc[page_num]
        text_dict = page.get_text("dict", clip=pdf_rect)

        font_name = None
        font_size = None

        for block in text_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        font_name = span.get("font")
                        font_size = span.get("size")
                        break
                if font_name: break
            if font_name: break

        if not font_name: return None, None

        lower = font_name.lower().replace("-", " ").replace("  ", " ")
        if "+" in font_name:
            clean = font_name.split("+", 1)[1]
        else:
            clean = font_name

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

    # ------------------------------------------------------------------
    # Overlay CRUD
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
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

                font_name = o.get("font_name", "helv")
                fontref = self._resolve_fontref(font_name, page, registered_fonts)
                tr, tg, tb = self._hex_to_rgb(o.get("text_color", "#000000"))
                font_size = max(4, int(o.get("font_size", 12)))

                result = page.insert_textbox(rect, text, fontname=fontref, fontsize=font_size, color=(tr, tg, tb),
                                             align=fitz.TEXT_ALIGN_LEFT)
                if result < 0:
                    page.insert_text(fitz.Point(x0 + 1, y0 + font_size), text, fontname=fontref, fontsize=font_size,
                                     color=(tr, tg, tb))

        # FIXED: Removed self.doc.close() to allow multiple saves/edits without crashing
        self.doc.save(output_path, garbage=4, deflate=True)

    def _resolve_fontref(self, font_name, page, registered):
        if font_name in registered: return registered[font_name]
        builtin_map = {"helv": "helv", "tiro": "tiro", "cour": "cour", "symb": "symb", "zadb": "zadb",
                       "helvetica": "helv", "arial": "helv", "times-roman": "tiro", "times": "tiro", "courier": "cour"}
        lower = font_name.lower()
        for alias, ref in builtin_map.items():
            if alias in lower:
                registered[font_name] = ref
                return ref

        if font_name in self.custom_fonts:
            info = self.custom_fonts[font_name]
            ref = info["ref_name"]
            try:
                page.insert_font(fontname=ref, fontfile=info["temp_path"])
                registered[font_name] = ref
                return ref
            except Exception as e:
                print(f"[PDFEngine] insert_font failed: {e}")

        registered[font_name] = "helv"
        return "helv"

    def _hex_to_rgb(self, hex_color):
        if not hex_color or hex_color == "transparent": return (1.0, 1.0, 1.0)
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3: hex_color = "".join(c * 2 for c in hex_color)
        return (int(hex_color[0:2], 16) / 255.0, int(hex_color[2:4], 16) / 255.0, int(hex_color[4:6], 16) / 255.0)
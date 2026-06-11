import sys
import uuid
import os
import tempfile
import fitz
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QGraphicsPixmapItem,
    QColorDialog, QSpinBox, QComboBox,
    QMessageBox, QInputDialog, QDialog
)
from PySide6.QtGui import (
    QPixmap, QColor, QFont, QPen, QBrush, QImage, QCursor, QPainter, QFontDatabase, QTextOption
)
from PySide6.QtCore import Qt, QPointF, QRectF, QPoint
from pdf_engine import PDFOverlayEngine

class SignatureCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StaticContents)
        self.modified = False
        self.scribbling = False
        self.myPenWidth = 3
        self.myPenColor = QColor("#000080")
        self.bgColor = QColor(0, 0, 0, 0)
        self.image = QImage(400, 200, QImage.Format.Format_ARGB32)
        self.clearImage()
        self.setMinimumSize(400, 200)

    def set_pen_color(self, color):
        self.myPenColor = color

    def set_bg_color(self, color):
        self.bgColor = color
        self.clearImage()

    def clearImage(self):
        self.image.fill(self.bgColor)
        self.modified = True
        self.update()

    def saveImage(self, filePath):
        self.image.save(filePath, "PNG")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(0, 0, self.image)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.lastPoint = event.pos()
            self.scribbling = True

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton) and self.scribbling:
            painter = QPainter(self.image)
            painter.setPen(QPen(self.myPenColor, self.myPenWidth, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(self.lastPoint, event.pos())
            self.modified = True
            self.lastPoint = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.scribbling:
            painter = QPainter(self.image)
            painter.setPen(QPen(self.myPenColor, self.myPenWidth, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(self.lastPoint, event.pos())
            self.scribbling = False

class SignatureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Draw Your Signature")
        self.resize(450, 350)
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.btn_pen_color = QPushButton("🖊️ Pen Color")
        self.btn_pen_color.clicked.connect(self.choose_pen_color)
        toolbar.addWidget(self.btn_pen_color)
        self.btn_bg_color = QPushButton("🎨 Background Color")
        self.btn_bg_color.clicked.connect(self.choose_bg_color)
        toolbar.addWidget(self.btn_bg_color)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.canvas = SignatureCanvas()
        layout.addWidget(self.canvas)
        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.canvas.clearImage)
        self.btn_save = QPushButton("Insert Signature")
        self.btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        self.temp_path = os.path.join(tempfile.gettempdir(), f"signature_{uuid.uuid4().hex}.png")

    def choose_pen_color(self):
        color = QColorDialog.getColor(self.canvas.myPenColor, self, "Select Pen Color")
        if color.isValid(): self.canvas.set_pen_color(color)

    def choose_bg_color(self):
        options = ["Transparent", "White", "Yellow"]
        choice, ok = QInputDialog.getItem(self, "Background Color", "Choose background: ", options, 0, False)
        if ok:
            if choice == "Transparent": self.canvas.set_bg_color(QColor(0, 0, 0, 0))
            elif choice == "White": self.canvas.set_bg_color(QColor(255, 255, 255))
            elif choice == "Yellow": self.canvas.set_bg_color(QColor(255, 255, 0))

    def accept(self):
        if self.canvas.modified:
            self.canvas.saveImage(self.temp_path)
            super().accept()
        else:
            QMessageBox.warning(self, "Empty Signature", "Please draw a signature first.")

class CustomGraphicsView(QGraphicsView):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._drag_start = None
        self._selection_rect = None

    def mousePressEvent(self, event):
        if self.main_window.color_picker_mode and event.button() == Qt.MouseButton.LeftButton:
            self.main_window.handle_bg_color_pick(event.pos())
            event.accept()
            return
        if self.main_window.picker_mode and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = self.mapToScene(event.pos())
            self._selection_rect = QGraphicsRectItem()
            self._selection_rect.setPen(QPen(QColor("#FF9800"), 2, Qt.PenStyle.DashLine))
            self._selection_rect.setBrush(QBrush(QColor(255, 152, 0, 50)))
            self.scene().addItem(self._selection_rect)
            self._selection_rect.setRect(QRectF(self._drag_start.x(), self._drag_start.y(), 0, 0))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.main_window.picker_mode and self._drag_start is not None:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self._drag_start, current_pos).normalized()
            self._selection_rect.setRect(rect)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.main_window.picker_mode and event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            end_pos = self.mapToScene(event.pos())
            rect = QRectF(self._drag_start, end_pos).normalized()
            if self._selection_rect:
                self.scene().removeItem(self._selection_rect)
                self._selection_rect = None
            self._drag_start = None
            if rect.width() < 5 or rect.height() < 5:
                rect = QRectF(end_pos.x() - 15, end_pos.y() - 15, 30, 30)
            self.main_window.handle_font_pick(rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

class EditableText(QGraphicsTextItem):
    def __init__(self, parent_box):
        super().__init__(parent_box)
        self.parent_box = parent_box

    def focusOutEvent(self, event):
        self.parent_box.overlay_data["text"] = self.toPlainText()
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.parent_box.overlay_data["text"] = self.toPlainText()
            self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.clearFocus()
        else:
            super().keyPressEvent(event)

class ResizeHandle(QGraphicsRectItem):
    SIZE = 9
    CURSORS = {
        "tl": Qt.CursorShape.SizeFDiagCursor, "tr": Qt.CursorShape.SizeBDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
        "ml": Qt.CursorShape.SizeHorCursor, "mr": Qt.CursorShape.SizeHorCursor,
        "mt": Qt.CursorShape.SizeVerCursor, "mb": Qt.CursorShape.SizeVerCursor
    }
    def __init__(self, parent_box, corner):
        s = self.SIZE
        super().__init__(-s / 2, -s / 2, s, s, parent_box)
        self.parent_box = parent_box
        self.corner = corner
        self.setPen(QPen(QColor("#1565C0"), 1))
        self.setBrush(QBrush(QColor("#FFFFFF")))
        self.setCursor(self.CURSORS.get(corner, Qt.CursorShape.SizeAllCursor))
        self.setZValue(20)
        self.setAcceptHoverEvents(True)
        self._drag_start = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self._drag_start = event.scenePos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            delta = event.scenePos() - self._drag_start
            self._drag_start = event.scenePos()
            self.parent_box.apply_resize(self.corner, delta)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        event.accept()

class DraggableTextItem(QGraphicsRectItem):
    MIN_W = 60
    MIN_H = 25
    def __init__(self, overlay_data, parent=None):
        super().__init__(parent)
        self.overlay_data = overlay_data
        self.overlay_data.setdefault("text_alignment", int(Qt.AlignmentFlag.AlignLeft))
        self.overlay_data.setdefault("font_bold", False)
        self.overlay_data.setdefault("font_italic", False)
        self.overlay_data.setdefault("font_underline", False)
        self.overlay_data.setdefault("qt_font_family", "Arial")

        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(QColor("#2196F3"), 2, Qt.PenStyle.DashLine))
        self._refresh_brush()

        self.text_item = EditableText(self)
        self.text_item.setPlainText(overlay_data["text"])
        self.text_item.setDefaultTextColor(QColor(overlay_data["text_color"]))

        font_family = overlay_data.get("qt_font_family", "Arial")
        font_size = overlay_data.get("font_size", 12)
        _init_font = QFont(font_family, font_size)
        _init_font.setBold(overlay_data.get("font_bold", False))
        _init_font.setItalic(overlay_data.get("font_italic", False))
        _init_font.setUnderline(overlay_data.get("font_underline", False))
        self.text_item.setFont(_init_font)

        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.text_item.setPos(5, 2)

        w = float(overlay_data.get("width", 150))
        h = float(overlay_data.get("height", 40))
        self.setRect(0, 0, w, h)

        self._handles = {}
        for corner in ("tl", "tr", "bl", "br", "ml", "mr", "mt", "mb"):
            handle = ResizeHandle(self, corner)
            handle.setVisible(False)
            self._handles[corner] = handle

        self._update_text_layout()
        self._reposition_handles()

    def _refresh_brush(self):
        bg = self.overlay_data.get("bg_color", "transparent")
        self.setBrush(QBrush(QColor(bg)) if bg and bg != "transparent" else QBrush(Qt.BrushStyle.NoBrush))

    def _reposition_handles(self):
        r = self.rect()
        cx, cy = r.center().x(), r.center().y()
        positions = {
            "tl": QPointF(r.left(), r.top()), "tr": QPointF(r.right(), r.top()),
            "bl": QPointF(r.left(), r.bottom()), "br": QPointF(r.right(), r.bottom()),
            "ml": QPointF(r.left(), cy), "mr": QPointF(r.right(), cy),
            "mt": QPointF(cx, r.top()), "mb": QPointF(cx, r.bottom())
        }
        for name, pos in positions.items(): self._handles[name].setPos(pos)

    def apply_resize(self, corner, delta):
        r = self.rect()
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        if "r" in corner:
            w = max(self.MIN_W, w + delta.x())
        elif "l" in corner:
            new_w = max(self.MIN_W, w - delta.x())
            if new_w != w: self.moveBy(delta.x(), 0); w = new_w
        if "b" in corner:
            h = max(self.MIN_H, h + delta.y())
        elif "t" in corner:
            new_h = max(self.MIN_H, h - delta.y())
            if new_h != h: self.moveBy(0, delta.y()); h = new_h

        self.setRect(x, y, w, h)
        self._reposition_handles()
        self.overlay_data["width"] = w
        self.overlay_data["height"] = h
        self._fit_text_to_box()

    def _update_text_layout(self):
        option = QTextOption()
        align_flag = Qt.AlignmentFlag(self.overlay_data.get("text_alignment", int(Qt.AlignmentFlag.AlignLeft)))
        option.setAlignment(align_flag)
        self.text_item.document().setDefaultTextOption(option)
        self.text_item.setTextWidth(max(10.0, self.rect().width() - 10))

    def _fit_text_to_box(self):
        target_w = max(20.0, self.rect().width() - 10)
        target_h = max(20.0, self.rect().height() - 4)
        self.text_item.setTextWidth(target_w)

        low, high = 4, 96
        best_size = self.overlay_data.get("font_size", 12)
        font_family = self.overlay_data.get("qt_font_family", "Arial")

        _is_bold = self.overlay_data.get("font_bold", False)
        _is_italic = self.overlay_data.get("font_italic", False)
        _is_underline = self.overlay_data.get("font_underline", False)
        while low <= high:
            mid = (low + high) // 2
            test_font = QFont(font_family, mid)
            test_font.setBold(_is_bold)
            test_font.setItalic(_is_italic)
            self.text_item.setFont(test_font)
            if self.text_item.document().size().height() <= target_h:
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1

        final_font = QFont(font_family, best_size)
        final_font.setBold(_is_bold)
        final_font.setItalic(_is_italic)
        final_font.setUnderline(_is_underline)

        self.text_item.setFont(final_font)
        self.overlay_data["font_size"] = best_size

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            self.overlay_data["x"] = self.pos().x()
            self.overlay_data["y"] = self.pos().y()
        elif change == QGraphicsRectItem.GraphicsItemChange.ItemSelectedHasChanged:
            visible = bool(value)
            for h in self._handles.values(): h.setVisible(visible)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.text_item.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def update_style(self, new_data):
        self.overlay_data.update(new_data)
        if "text" in new_data:
            self.text_item.setPlainText(self.overlay_data["text"])
        if "text_color" in new_data:
            self.text_item.setDefaultTextColor(QColor(self.overlay_data["text_color"]))

        if any(k in new_data for k in ["font_size", "font_name", "qt_font_family", "font_bold", "font_italic", "font_underline", "text_alignment"]):
            font_family = self.overlay_data.get("qt_font_family", "Arial")
            font_size = self.overlay_data.get("font_size", 12)
            font = QFont(font_family, font_size)
            font.setBold(self.overlay_data.get("font_bold", False))
            font.setItalic(self.overlay_data.get("font_italic", False))
            font.setUnderline(self.overlay_data.get("font_underline", False))
            self.text_item.setFont(font)
            self._update_text_layout()

        if "bg_color" in new_data:
            self._refresh_brush()

    def sync_text(self):
        self.overlay_data["text"] = self.text_item.toPlainText()

class DraggableImageItem(QGraphicsRectItem):
    MIN_W = 50
    MIN_H = 20
    def __init__(self, overlay_data, parent=None):
        super().__init__(parent)
        self.overlay_data = overlay_data
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(QColor("#4CAF50"), 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.pixmap = QPixmap()
        if overlay_data.get("image_path") and os.path.exists(overlay_data["image_path"]):
            self.pixmap = QPixmap(overlay_data["image_path"])
        w = float(overlay_data.get("width", 150))
        h = float(overlay_data.get("height", 50))
        self.setRect(0, 0, w, h)
        self._handles = {}
        for corner in ("tl", "tr", "bl", "br", "ml", "mr", "mt", "mb"):
            handle = ResizeHandle(self, corner)
            handle.setVisible(False)
            self._handles[corner] = handle
        self._reposition_handles()

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if not self.pixmap.isNull():
            scaled = self.pixmap.scaled(self.rect().size().toSize(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            offset_x = (self.rect().width() - scaled.width()) / 2
            offset_y = (self.rect().height() - scaled.height()) / 2
            painter.drawPixmap(offset_x, offset_y, scaled)

    def _reposition_handles(self):
        r = self.rect()
        cx, cy = r.center().x(), r.center().y()
        positions = {
            "tl": QPointF(r.left(), r.top()), "tr": QPointF(r.right(), r.top()),
            "bl": QPointF(r.left(), r.bottom()), "br": QPointF(r.right(), r.bottom()),
            "ml": QPointF(r.left(), cy), "mr": QPointF(r.right(), cy),
            "mt": QPointF(cx, r.top()), "mb": QPointF(cx, r.bottom())
        }
        for name, pos in positions.items(): self._handles[name].setPos(pos)

    def apply_resize(self, corner, delta):
        r = self.rect()
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        if "r" in corner:
            w = max(self.MIN_W, w + delta.x())
        elif "l" in corner:
            new_w = max(self.MIN_W, w - delta.x())
            if new_w != w: self.moveBy(delta.x(), 0); w = new_w
        if "b" in corner:
            h = max(self.MIN_H, h + delta.y())
        elif "t" in corner:
            new_h = max(self.MIN_H, h - delta.y())
            if new_h != h: self.moveBy(0, delta.y()); h = new_h
        self.setRect(x, y, w, h)
        self._reposition_handles()
        self.overlay_data["width"] = w
        self.overlay_data["height"] = h

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            self.overlay_data["x"] = self.pos().x()
            self.overlay_data["y"] = self.pos().y()
        elif change == QGraphicsRectItem.GraphicsItemChange.ItemSelectedHasChanged:
            visible = bool(value)
            for h in self._handles.values(): h.setVisible(visible)
        return super().itemChange(change, value)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Form Filler & Annotator")
        self.resize(1200, 800)
        self.engine: PDFOverlayEngine | None = None
        self.current_page = 0
        self.zoom = 2.0
        self.picker_mode = False
        self.color_picker_mode = False
        self.current_text_item = None
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.scene = QGraphicsScene()
        self.view = CustomGraphicsView(self)
        self.view.setScene(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setStyleSheet("background-color: #808080;")
        main_layout.addWidget(self.view, stretch=4)

        right_panel = QWidget()
        right_panel.setFixedWidth(295)
        rl = QVBoxLayout(right_panel)
        rl.setSpacing(6)

        self.btn_open = QPushButton("📂 Open PDF")
        self.btn_open.clicked.connect(self.open_pdf)
        rl.addWidget(self.btn_open)

        nav = QWidget()
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_prev = QPushButton("◀ Prev")
        self.btn_prev.setEnabled(False)
        self.btn_prev.clicked.connect(self.prev_page)
        self.page_label = QLabel("No PDF loaded")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton("Next ▶")
        self.btn_next.setEnabled(False)
        self.btn_next.clicked.connect(self.next_page)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.page_label, stretch=1)
        nav_layout.addWidget(self.btn_next)
        rl.addWidget(nav)

        page_mgmt_layout = QHBoxLayout()
        self.btn_insert_page = QPushButton("➕ Insert Page")
        self.btn_insert_page.clicked.connect(self.insert_blank_page)
        self.btn_insert_page.setEnabled(False)
        self.btn_delete_page = QPushButton("🗑️ Delete Page")
        self.btn_delete_page.setStyleSheet("background-color: #f44336; color: white;")
        self.btn_delete_page.clicked.connect(self.delete_current_page)
        self.btn_delete_page.setEnabled(False)
        page_mgmt_layout.addWidget(self.btn_insert_page)
        page_mgmt_layout.addWidget(self.btn_delete_page)
        rl.addLayout(page_mgmt_layout)

        self.btn_append_pdf = QPushButton("📑 Append Pages from PDF")
        self.btn_append_pdf.clicked.connect(self.append_pdf_pages)
        self.btn_append_pdf.setEnabled(False)
        rl.addWidget(self.btn_append_pdf)

        self.btn_add_text = QPushButton("➕ Add Text Box")
        self.btn_add_text.clicked.connect(self.add_text_box)
        self.btn_add_text.setEnabled(False)
        rl.addWidget(self.btn_add_text)

        self.btn_add_image = QPushButton("🖼️ Insert Image")
        self.btn_add_image.clicked.connect(self.insert_image)
        self.btn_add_image.setEnabled(False)
        rl.addWidget(self.btn_add_image)

        self.btn_add_signature = QPushButton("✍️ Draw Signature")
        self.btn_add_signature.setStyleSheet("background-color: #E91E63; color: white; font-weight: bold;")
        self.btn_add_signature.clicked.connect(self.draw_signature)
        self.btn_add_signature.setEnabled(False)
        rl.addWidget(self.btn_add_signature)

        rl.addWidget(QLabel("<hr>"))
        rl.addWidget(QLabel("<b>Font Settings:</b>"))

        self.font_combo = QComboBox()
        self.font_combo.addItems(["Arial", "Times New Roman", "Courier New"])
        self.font_combo.currentTextChanged.connect(self.update_selected_box_font)
        rl.addWidget(self.font_combo)

        self.btn_pick_font = QPushButton("🖌️ Pick Font from PDF")
        self.btn_pick_font.setStyleSheet("background-color: #FF9800; color: white;")
        self.btn_pick_font.clicked.connect(self.toggle_picker_mode)
        rl.addWidget(self.btn_pick_font)

        style_layout = QHBoxLayout()
        self.btn_bold = QPushButton("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setFixedSize(30, 30)
        self.btn_bold.clicked.connect(lambda: self.toggle_font_style("bold"))

        self.btn_italic = QPushButton("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setFixedSize(30, 30)
        self.btn_italic.clicked.connect(lambda: self.toggle_font_style("italic"))

        self.btn_underline = QPushButton("U")
        self.btn_underline.setCheckable(True)
        self.btn_underline.setFixedSize(30, 30)
        self.btn_underline.clicked.connect(lambda: self.toggle_font_style("underline"))

        style_layout.addWidget(self.btn_bold)
        style_layout.addWidget(self.btn_italic)
        style_layout.addWidget(self.btn_underline)

        self.btn_align_left = QPushButton("L")
        self.btn_align_left.setCheckable(True)
        self.btn_align_left.setFixedSize(30, 30)
        self.btn_align_left.setChecked(True)
        self.btn_align_left.clicked.connect(lambda: self.set_text_alignment(Qt.AlignmentFlag.AlignLeft))

        self.btn_align_center = QPushButton("C")
        self.btn_align_center.setCheckable(True)
        self.btn_align_center.setFixedSize(30, 30)
        self.btn_align_center.clicked.connect(lambda: self.set_text_alignment(Qt.AlignmentFlag.AlignCenter))

        self.btn_align_right = QPushButton("R")
        self.btn_align_right.setCheckable(True)
        self.btn_align_right.setFixedSize(30, 30)
        self.btn_align_right.clicked.connect(lambda: self.set_text_alignment(Qt.AlignmentFlag.AlignRight))

        style_layout.addSpacing(10)
        style_layout.addWidget(self.btn_align_left)
        style_layout.addWidget(self.btn_align_center)
        style_layout.addWidget(self.btn_align_right)
        style_layout.addStretch()
        rl.addLayout(style_layout)

        rl.addWidget(QLabel("<hr>"))
        rl.addWidget(QLabel("<b>Selected Box Properties:</b>"))

        self.prop_text = QLabel("Click a box to select it.\nDouble-click to edit text.")
        self.prop_text.setStyleSheet("color: gray; font-style: italic; font-size: 12px;")
        self.prop_text.setWordWrap(True)
        rl.addWidget(self.prop_text)

        self.prop_font_size = QSpinBox()
        self.prop_font_size.setRange(6, 96)
        self.prop_font_size.setValue(12)
        self.prop_font_size.valueChanged.connect(self.update_selected_box_size)
        rl.addWidget(self.prop_font_size)

        self.btn_text_color = QPushButton("🎨 Choose Text Color")
        self.btn_text_color.clicked.connect(lambda: self.choose_color("text"))
        rl.addWidget(self.btn_text_color)

        self.btn_bg_color = QPushButton("🎨 Choose BG Color")
        self.btn_bg_color.clicked.connect(lambda: self.choose_color("bg"))
        rl.addWidget(self.btn_bg_color)

        self.btn_pick_bg_color = QPushButton("💧 Pick BG Color from PDF")
        self.btn_pick_bg_color.setStyleSheet("background-color: #9C27B0; color: white;")
        self.btn_pick_bg_color.clicked.connect(self.toggle_color_picker_mode)
        rl.addWidget(self.btn_pick_bg_color)

        self.btn_delete = QPushButton("🗑️ Delete Selected Box")
        self.btn_delete.setStyleSheet("background-color: #f44336; color: white;")
        self.btn_delete.clicked.connect(self.delete_selected_box)
        rl.addWidget(self.btn_delete)

        rl.addStretch()

        self.btn_save = QPushButton("💾 Save PDF")
        self.btn_save.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.btn_save.clicked.connect(self.save_pdf)
        self.btn_save.setEnabled(False)
        rl.addWidget(self.btn_save)

        main_layout.addWidget(right_panel)
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def open_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if not file_path: return
        try:
            self.engine = PDFOverlayEngine(file_path)
            self.current_page = 0
            self.render_current_page()
            self._enable_tools(True)
            self._update_page_label()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open PDF:\n{e}")

    def _enable_tools(self, enabled):
        self.btn_add_text.setEnabled(enabled)
        self.btn_add_image.setEnabled(enabled)
        self.btn_add_signature.setEnabled(enabled)
        self.btn_insert_page.setEnabled(enabled)
        self.btn_delete_page.setEnabled(enabled)
        self.btn_append_pdf.setEnabled(enabled)
        self.btn_save.setEnabled(enabled)
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)

    def prev_page(self):
        if self.engine and self.current_page > 0:
            self._sync_all_text()
            self.current_page -= 1
            self.render_current_page()
            self._update_page_label()

    def next_page(self):
        if self.engine and self.current_page < self.engine.get_page_count() - 1:
            self._sync_all_text()
            self.current_page += 1
            self.render_current_page()
            self._update_page_label()

    def _update_page_label(self):
        if self.engine:
            total = self.engine.get_page_count()
            self.page_label.setText(f"Page {self.current_page + 1} / {total}")
            self.btn_prev.setEnabled(self.current_page > 0)
            self.btn_next.setEnabled(self.current_page < total - 1)

    def _sync_all_text(self):
        for item in self.scene.items():
            if isinstance(item, DraggableTextItem): item.sync_text()

    def render_current_page(self):
        self.scene.clear()
        self.current_text_item = None
        if self.engine.get_page_count() == 0: return
        pixmap = self.engine.render_page_to_pixmap(self.current_page, zoom=self.zoom)
        q_img = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format.Format_RGB888)
        pm = QPixmap.fromImage(q_img)
        self.scene.addPixmap(pm)
        self.scene.setSceneRect(0, 0, pm.width(), pm.height())
        for o_data in self.engine.get_overlays_for_page(self.current_page):
            item = DraggableImageItem(o_data) if o_data.get("image_path") else DraggableTextItem(o_data)
            item.setPos(o_data["x"], o_data["y"])
            self.scene.addItem(item)

    def delete_current_page(self):
        if not self.engine: return
        if self.engine.get_page_count() == 1:
            QMessageBox.warning(self, "Cannot Delete", "You cannot delete the last page of the document.")
            return
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete Page {self.current_page + 1}? This cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.engine.delete_page(self.current_page)
            if self.current_page >= self.engine.get_page_count(): self.current_page = self.engine.get_page_count() - 1
            self.render_current_page()
            self._update_page_label()

    def insert_blank_page(self):
        if not self.engine: return
        new_idx = self.engine.insert_blank_page(self.current_page)
        self._sync_all_text()
        self.current_page = new_idx
        self.render_current_page()
        self._update_page_label()

    def append_pdf_pages(self):
        if not self.engine: return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select PDF to Append", "", "PDF Files (*.pdf)")
        if not file_path: return
        try:
            self.engine.append_pdf(file_path)
            QMessageBox.information(self, "Success", "Pages appended successfully!")
            self._update_page_label()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to append PDF:\n{e}")

    def add_text_box(self):
        overlay_data = {
            "id": str(uuid.uuid4()), "text": "New Text", "x": 50.0, "y": 50.0, "width": 150.0, "height": 40.0,
            "font_size": 12, "font_name": "helv", "qt_font_family": "Arial", "text_color": "#000000",
            "bg_color": "transparent", "font_bold": False, "font_italic": False, "font_underline": False,
            "text_alignment": int(Qt.AlignmentFlag.AlignLeft)
        }
        item = DraggableTextItem(overlay_data)
        item.setPos(overlay_data["x"], overlay_data["y"])
        self.scene.addItem(item)
        self.engine.add_overlay(self.current_page, overlay_data)
        self.scene.clearSelection()
        item.setSelected(True)

    def insert_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Insert Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not file_path: return
        overlay_data = {"id": str(uuid.uuid4()), "image_path": file_path, "x": 100.0, "y": 100.0, "width": 150.0, "height": 100.0}
        item = DraggableImageItem(overlay_data)
        item.setPos(overlay_data["x"], overlay_data["y"])
        self.scene.addItem(item)
        self.engine.add_overlay(self.current_page, overlay_data)
        self.scene.clearSelection()
        item.setSelected(True)

    def draw_signature(self):
        dialog = SignatureDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            overlay_data = {"id": str(uuid.uuid4()), "image_path": dialog.temp_path, "x": 100.0, "y": 100.0, "width": 150.0, "height": 75.0}
            item = DraggableImageItem(overlay_data)
            item.setPos(overlay_data["x"], overlay_data["y"])
            self.scene.addItem(item)
            self.engine.add_overlay(self.current_page, overlay_data)
            self.scene.clearSelection()
            item.setSelected(True)

    def on_selection_changed(self):
        boxes = [i for i in self.scene.selectedItems() if isinstance(i, (DraggableTextItem, DraggableImageItem))]
        if boxes:
            self.current_text_item = boxes[0]
            is_image = isinstance(self.current_text_item, DraggableImageItem)

            for widget in [self.prop_font_size, self.btn_text_color, self.btn_bg_color, self.btn_pick_bg_color,
                           self.font_combo, self.btn_pick_font, self.btn_bold, self.btn_italic, self.btn_underline,
                           self.btn_align_left, self.btn_align_center, self.btn_align_right]:
                widget.setVisible(not is_image)

            if not is_image and isinstance(self.current_text_item, DraggableTextItem):
                data = self.current_text_item.overlay_data

                self.prop_font_size.blockSignals(True)
                self.prop_font_size.setValue(data.get("font_size", 12))
                self.prop_font_size.blockSignals(False)

                display_name = data.get("qt_font_family", "Arial")
                self.font_combo.blockSignals(True)
                idx = self.font_combo.findText(display_name)
                if idx != -1: self.font_combo.setCurrentIndex(idx)
                self.font_combo.blockSignals(False)

                self.btn_bold.blockSignals(True)
                self.btn_bold.setChecked(data.get("font_bold", False))
                self.btn_bold.blockSignals(False)

                self.btn_italic.blockSignals(True)
                self.btn_italic.setChecked(data.get("font_italic", False))
                self.btn_italic.blockSignals(False)

                self.btn_underline.blockSignals(True)
                self.btn_underline.setChecked(data.get("font_underline", False))
                self.btn_underline.blockSignals(False)

                align = data.get("text_alignment", int(Qt.AlignmentFlag.AlignLeft))
                self.btn_align_left.blockSignals(True)
                self.btn_align_left.setChecked(align == int(Qt.AlignmentFlag.AlignLeft))
                self.btn_align_left.blockSignals(False)

                self.btn_align_center.blockSignals(True)
                self.btn_align_center.setChecked(align == int(Qt.AlignmentFlag.AlignCenter))
                self.btn_align_center.blockSignals(False)

                self.btn_align_right.blockSignals(True)
                self.btn_align_right.setChecked(align == int(Qt.AlignmentFlag.AlignRight))
                self.btn_align_right.blockSignals(False)

            self.prop_text.setText("Drag corners to resize.\nDrag center to move.")
            self.prop_text.setStyleSheet("color: black; font-style: normal; font-size: 12px;")
        else:
            self.current_text_item = None
            for widget in [self.prop_font_size, self.btn_text_color, self.btn_bg_color, self.btn_pick_bg_color,
                            self.font_combo, self.btn_pick_font, self.btn_bold, self.btn_italic, self.btn_underline,
                           self.btn_align_left, self.btn_align_center, self.btn_align_right]:
                widget.setVisible(True)
            self.prop_text.setText("Click a box to select it.")
            self.prop_text.setStyleSheet("color: gray; font-style: italic; font-size: 12px;")

    def update_selected_box_font(self, font_display_name):
        if not self.current_text_item or isinstance(self.current_text_item, DraggableImageItem): return
        font_map = {"Arial": "helv", "Times New Roman": "tiro", "Courier New": "cour"}
        # Resolve the PDF engine font_name: use known mapping, otherwise preserve existing
        existing_font_name = self.current_text_item.overlay_data.get("font_name", "helv")
        resolved_font_name = font_map.get(font_display_name, existing_font_name)
        new_data = {"qt_font_family": font_display_name, "font_name": resolved_font_name}
        self.current_text_item.update_style(new_data)
        self.engine.update_overlay(self.current_page, self.current_text_item.overlay_data["id"], new_data)

    def update_selected_box_size(self):
        if not self.current_text_item or isinstance(self.current_text_item, DraggableImageItem): return
        new_data = {"font_size": self.prop_font_size.value()}
        self.current_text_item.update_style(new_data)
        self.engine.update_overlay(self.current_page, self.current_text_item.overlay_data["id"], new_data)

    def choose_color(self, target):
        target_item = self.current_text_item
        if not target_item or isinstance(target_item, DraggableImageItem):
            QMessageBox.warning(self, "Warning", "Please select a text box first.")
            return
        new_data = {}
        if target == "bg":
            options = ["Transparent", "White", "Yellow", "Custom…"]
            choice, ok = QInputDialog.getItem(self, "Background Color", "Choose a background: ", options, 0, False)
            if not ok: return
            if choice == "Transparent": new_data = {"bg_color": "transparent"}
            elif choice == "White": new_data = {"bg_color": "#FFFFFF"}
            elif choice == "Yellow": new_data = {"bg_color": "#FFFF00"}
            else:
                color = QColorDialog.getColor(parent=self)
                if not color.isValid(): return
                new_data = {"bg_color": color.name()}
        else:
            initial = QColor(target_item.overlay_data.get("text_color", "#000000"))
            color = QColorDialog.getColor(initial, parent=self)
            if not color.isValid(): return
            new_data = {"text_color": color.name()}
        target_item.update_style(new_data)
        self.engine.update_overlay(self.current_page, target_item.overlay_data["id"], new_data)
        self.scene.clearSelection()
        target_item.setSelected(True)
        self.current_text_item = target_item

    def delete_selected_box(self):
        if not self.current_text_item: return
        self.engine.remove_overlay(self.current_page, self.current_text_item.overlay_data["id"])
        self.scene.removeItem(self.current_text_item)
        self.current_text_item = None

    def toggle_picker_mode(self):
        if not self.current_text_item or isinstance(self.current_text_item, DraggableImageItem):
            QMessageBox.warning(self, "Warning", "Select a text box first, then use the font picker.")
            return
        self.picker_mode = not self.picker_mode
        if self.picker_mode:
            self.btn_pick_font.setText("❌ Cancel Font Picker")
            self.btn_pick_font.setStyleSheet("background-color: #f44336; color: white;")
            self.view.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.btn_pick_font.setText("🖌️ Pick Font from PDF")
            self.btn_pick_font.setStyleSheet("background-color: #FF9800; color: white;")
            self.view.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def toggle_color_picker_mode(self):
        if not self.current_text_item or isinstance(self.current_text_item, DraggableImageItem):
            QMessageBox.warning(self, "Warning", "Select a text box first, then use the color picker.")
            return
        self.color_picker_mode = not self.color_picker_mode
        if self.color_picker_mode:
            self.btn_pick_bg_color.setText("❌ Cancel Color Picker")
            self.btn_pick_bg_color.setStyleSheet("background-color: #f44336; color: white;")
            self.view.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.btn_pick_bg_color.setText("💧 Pick BG Color from PDF")
            self.btn_pick_bg_color.setStyleSheet("background-color: #9C27B0; color: white;")
            self.view.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def handle_font_pick(self, scene_rect: QRectF):
        pdf_x0 = scene_rect.left() / self.zoom
        pdf_y0 = scene_rect.top() / self.zoom
        pdf_x1 = scene_rect.right() / self.zoom
        pdf_y1 = scene_rect.bottom() / self.zoom
        pdf_rect = fitz.Rect(pdf_x0, pdf_y0, pdf_x1, pdf_y1)
        target_item = self.current_text_item

        self.picker_mode = False
        self.btn_pick_font.setText("🖌️ Pick Font from PDF")
        self.btn_pick_font.setStyleSheet("background-color: #FF9800; color: white;")
        self.view.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        font_name, font_size = self.engine.extract_font_in_rect(self.current_page, pdf_rect)
        if font_name and target_item and isinstance(target_item, DraggableTextItem):
            if font_name in self.engine.custom_fonts:
                font_path = self.engine.custom_fonts[font_name]["temp_path"]
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    qt_font_family = families[0] if families else font_name
                else:
                    qt_font_family = "Arial"
            else:
                font_map = {"helv": "Arial", "tiro": "Times New Roman", "cour": "Courier New"}
                qt_font_family = font_map.get(font_name, font_name)

            if self.font_combo.findText(qt_font_family) == -1: self.font_combo.addItem(qt_font_family)
            self.font_combo.blockSignals(True)
            self.font_combo.setCurrentText(qt_font_family)
            self.font_combo.blockSignals(False)

            new_data = {"font_name": font_name, "qt_font_family": qt_font_family}
            if font_size is not None: new_data["font_size"] = int(font_size)
            target_item.update_style(new_data)
            self.engine.update_overlay(self.current_page, target_item.overlay_data["id"], new_data)
            QMessageBox.information(self, "Font Picked", f"Font '{qt_font_family}' extracted and applied!")
        else:
            QMessageBox.warning(self, "Not Found", "No text found in the selected area.")

    def handle_bg_color_pick(self, view_pos: QPoint):
        self.color_picker_mode = False
        self.btn_pick_bg_color.setText("💧 Pick BG Color from PDF")
        self.btn_pick_bg_color.setStyleSheet("background-color: #9C27B0; color: white;")
        self.view.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        if not self.current_text_item or isinstance(self.current_text_item, DraggableImageItem):
            QMessageBox.warning(self, "Warning", "Select a text box first.")
            return
        scene_pos = self.view.mapToScene(view_pos)
        items = self.scene.items(scene_pos)
        pixmap_item = next((item for item in items if isinstance(item, QGraphicsPixmapItem)), None)
        if pixmap_item:
            pixmap = pixmap_item.pixmap()
            local_pos = pixmap_item.mapFromScene(scene_pos)
            x, y = int(local_pos.x()), int(local_pos.y())
            if 0 <= x < pixmap.width() and 0 <= y < pixmap.height():
                color = pixmap.toImage().pixelColor(x, y)
                hex_color = color.name()
                new_data = {"bg_color": hex_color}
                self.current_text_item.update_style(new_data)
                self.engine.update_overlay(self.current_page, self.current_text_item.overlay_data["id"], new_data)
                QMessageBox.information(self, "Color Picked", f"Background color set to {hex_color}")
            else:
                QMessageBox.warning(self, "Out of Bounds", "Clicked outside the page area.")
        else:
            QMessageBox.warning(self, "Not Found", "Could not detect page background at this location.")

    def set_text_alignment(self, alignment_flag):
        if not self.current_text_item or isinstance(self.current_text_item, DraggableImageItem): return
        self.btn_align_left.setChecked(alignment_flag == Qt.AlignmentFlag.AlignLeft)
        self.btn_align_center.setChecked(alignment_flag == Qt.AlignmentFlag.AlignCenter)
        self.btn_align_right.setChecked(alignment_flag == Qt.AlignmentFlag.AlignRight)

        new_data = {"text_alignment": int(alignment_flag)}
        self.current_text_item.update_style(new_data)
        self.engine.update_overlay(self.current_page, self.current_text_item.overlay_data["id"], new_data)

    def toggle_font_style(self, style):
        if not self.current_text_item or isinstance(self.current_text_item, DraggableImageItem): return
        new_data = {
            "font_bold": self.btn_bold.isChecked(),
            "font_italic": self.btn_italic.isChecked(),
            "font_underline": self.btn_underline.isChecked()
        }
        self.current_text_item.update_style(new_data)
        self.engine.update_overlay(self.current_page, self.current_text_item.overlay_data["id"], new_data)

    def save_pdf(self):
        if not self.engine: return
        self._sync_all_text()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if not file_path: return
        try:
            self.scene.clearSelection()
            self.engine.save(file_path, zoom=self.zoom)
            QMessageBox.information(self, "Saved", "PDF saved successfully with all overlays!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save PDF:\n{e}")
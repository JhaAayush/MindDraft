import sys
import os
import re
import markdown2
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTextEdit, QStatusBar,
    QFileDialog, QTextBrowser, QMessageBox, QTabWidget, QInputDialog
)
from PySide6.QtCore import Qt, QFileInfo, QMarginsF
from PySide6.QtGui import (
    QAction, QKeySequence, QTextDocument, QSyntaxHighlighter,
    QTextCharFormat, QColor, QFont, QPageLayout, QIcon ## --- IMPORT ADDED ---
)
from PySide6.QtPrintSupport import QPrinter


# --- Plain Text Editor ---
class PlainTextEditor(QTextEdit):
    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)


# --- Markdown Syntax Highlighter ---
class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.formats = {
            'heading': self._create_format(color="#C678DD", weight=QFont.Bold),
            'bold': self._create_format(weight=QFont.Bold, color="#E06C75"),
            'italic': self._create_format(italic=True, color="#98C379"),
            'strikethrough': self._create_format(strike=True, color="#5C6370"),
            'inline_code': self._create_format(color="#61AFEF", background_color="#3A3F4B"),
            'list_item': self._create_format(color="#E06C75"),
            'quote': self._create_format(italic=True, color="#5C6370"),
            'code_block': self._create_format(color="#ABB2BF"),
        }
        self.highlighting_rules = [
            (re.compile(r"^#{1,6}\s.*"), 'heading'),
            (re.compile(r"\*\*(.*?)\*\*"), 'bold'),
            (re.compile(r"__(.*?)__"), 'bold'),
            (re.compile(r"\*(.*?)\*"), 'italic'),
            (re.compile(r"_(.*?)_"), 'italic'),
            (re.compile(r"~{2}(.*?)~{2}"), 'strikethrough'),
            (re.compile(r"`(.*?)`"), 'inline_code'),
            (re.compile(r"^[*\-]\s"), 'list_item'),
            (re.compile(r"^\d+\.\s"), 'list_item'),
            (re.compile(r"^>.*"), 'quote'),
        ]
        self.code_block_start_expression = re.compile(r"^```.*")
        self.code_block_end_expression = re.compile(r"^```$")

    def _create_format(self, color, background_color=None, weight=None, italic=False, strike=False):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if background_color:
            fmt.setBackground(QColor(background_color))
        if weight:
            fmt.setFontWeight(weight)
        fmt.setFontItalic(italic)
        fmt.setFontStrikeOut(strike)
        return fmt

    def highlightBlock(self, text):
        for pattern, name in self.highlighting_rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), self.formats[name])
        self.setCurrentBlockState(0)
        if self.code_block_start_expression.match(text):
            self.setCurrentBlockState(1)
        elif self.previousBlockState() == 1 and not self.code_block_end_expression.match(text):
            self.setCurrentBlockState(1)
        if self.currentBlockState() == 1 or self.previousBlockState() == 1:
            self.setFormat(0, len(text), self.formats['code_block'])


# --- Main Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mind Draft")
        self.setGeometry(100, 100, 1200, 700)
        ## --- ICON ADDED HERE ---
        self.setWindowIcon(QIcon("book.png"))
        
        self.notes = []
        self.current_theme = 'dark'

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setTabShape(QTabWidget.TabShape.Rounded)
        self.tabs.tabCloseRequested.connect(self.close_note)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tabs)

        self._create_menu_bar()
        self._create_status_bar()
        self.new_note()

    def _get_current_widgets(self):
        current_tab_widget = self.tabs.currentWidget()
        if isinstance(current_tab_widget, QSplitter):
            return current_tab_widget.widget(0), current_tab_widget.widget(1)
        return None, None

    def _refresh_tab_text(self, index):
        if index < 0 or index >= len(self.notes):
            return
        note = self.notes[index]
        display_text = note['name'] + (" *" if note['is_dirty'] else "")
        self.tabs.setTabText(index, display_text)

    def on_text_changed(self):
        current_index = self.tabs.currentIndex()
        editor, preview = self._get_current_widgets()
        if current_index != -1 and editor and preview:
            self.notes[current_index]['is_dirty'] = True
            self.notes[current_index]['content'] = editor.toPlainText()
            self._refresh_tab_text(current_index)
            html = markdown2.markdown(
                editor.toPlainText(),
                extras=["fenced-code-blocks", "tables", "strike", "cuddled-lists", "codehilite"],
            )
            preview.setHtml(html)

    def _create_note_tab(self, name, content, path=None, is_dirty=False):
        editor = PlainTextEditor()
        editor.setText(content)
        preview = QTextBrowser()
        highlighter = MarkdownHighlighter(editor.document())
        editor.textChanged.connect(self.on_text_changed)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(editor)
        splitter.addWidget(preview)
        splitter.setSizes([600, 600])

        note_data = {
            'name': name,
            'content': content,
            'path': path,
            'is_dirty': is_dirty,
            'editor': editor,
            'preview': preview,
            'highlighter': highlighter,
        }
        self.notes.append(note_data)
        index = self.tabs.addTab(splitter, name)
        self.tabs.setCurrentIndex(index)
        return note_data

    def new_note(self):
        self._create_note_tab(f'Untitled Note {self.tabs.count() + 1}', "")
        self.statusBar().showMessage("New note created.")

    def open_note(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Note", "", "Markdown Files (*.md);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            note_name = QFileInfo(path).baseName()
            self._create_note_tab(note_name, content, path=path)
            self.statusBar().showMessage(f"Opened {note_name}")
        except Exception as e:
            self.statusBar().showMessage(f"Error opening file: {e}")

    def on_tab_changed(self, index):
        if index != -1:
            self.setWindowTitle(f"Mind Draft - {self.notes[index]['name']}")

    def close_note(self, index):
        note = self.notes[index]
        if note['is_dirty']:
            reply = QMessageBox.question(
                self,
                'Save Changes?',
                f"Save changes to {note['name']}?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_note():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        self.tabs.removeTab(index)
        del self.notes[index]
        if self.tabs.count() == 0:
            self.new_note()

    def close_current_note(self):
        if self.tabs.currentIndex() != -1:
            self.close_note(self.tabs.currentIndex())

    def rename_note(self):
        current_index = self.tabs.currentIndex()
        if current_index == -1:
            return
        note = self.notes[current_index]
        old_name = note['name']
        new_name, ok = QInputDialog.getText(
            self, "Rename Note", "New name:", text=old_name
        )
        if ok and new_name and new_name != old_name:
            note['name'] = new_name
            note['is_dirty'] = True
            if note['path']:
                try:
                    new_path = os.path.join(
                        os.path.dirname(note['path']), new_name + ".md"
                    )
                    os.rename(note['path'], new_path)
                    note['path'] = new_path
                except OSError as e:
                    QMessageBox.warning(
                        self, "Rename Error", f"Could not rename file: {e}"
                    )
                    note['name'] = old_name
            self._refresh_tab_text(current_index)
            self.setWindowTitle(f"Mind Draft - {note['name']}")

    def save_note(self):
        current_index = self.tabs.currentIndex()
        if current_index == -1:
            return False
        editor, _ = self._get_current_widgets()
        if not editor:
            return False
        note = self.notes[current_index]
        note['content'] = editor.toPlainText()
        if not note['path']:
            return self.save_note_as()
        try:
            with open(note['path'], 'w', encoding='utf-8') as f:
                f.write(note['content'])
            note['is_dirty'] = False
            self._refresh_tab_text(current_index)
            self.statusBar().showMessage(f"Saved {note['name']}")
            return True
        except Exception as e:
            self.statusBar().showMessage(f"Error saving file: {e}")
            return False

    def save_note_as(self):
        current_index = self.tabs.currentIndex()
        if current_index == -1:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Note As", "", "Markdown Files (*.md);;All Files (*)"
        )
        if path:
            note = self.notes[current_index]
            note['path'] = path
            note['name'] = QFileInfo(path).baseName()
            self._refresh_tab_text(current_index)
            self.setWindowTitle(f"Mind Draft - {note['name']}")
            return self.save_note()
        return False

    def export_pdf(self):
        current_index = self.tabs.currentIndex()
        if current_index == -1:
            return
        note = self.notes[current_index]
        markdown_text = note['content']
        if not markdown_text.strip():
            self.statusBar().showMessage("Cannot export an empty note.")
            return
        default_filename = note['name'] + ".pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", default_filename, "PDF Files (*.pdf)"
        )
        if not file_path:
            return
        html_fragment = markdown2.markdown(
            markdown_text,
            extras=["fenced-code-blocks", "tables", "strike", "cuddled-lists", "codehilite"],
        )
        pdf_css = """
            body { font-family: Segoe UI, sans-serif; font-size: 11pt; line-height: 1.5; color: #24292e; background: #ffffff; }
            h1 { font-size: 18pt; margin-top: 16px; }
            h2 { font-size: 14pt; margin-top: 12px; }
            pre, code { font-family: Consolas, monospace; font-size: 10pt; background: #f6f8fa; padding: 6px; border-radius: 4px; }
            table { border-collapse: collapse; width: 100%; font-size: 10pt; }
            th, td { border: 1px solid #cccccc; text-align: left; padding: 4px; }
            th { background-color: #f2f2f2; }
        """
        html_for_pdf = f"<html><head><meta charset='utf-8'/><style>{pdf_css}</style></head><body>{html_fragment}</body></html>"

        doc = QTextDocument()
        doc.setHtml(html_for_pdf)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter)

        doc.setPageSize(printer.pageRect(QPrinter.Point).size())
        doc.print_(printer)
        self.statusBar().showMessage(f"Successfully exported to {file_path}")

    def closeEvent(self, event):
        unsaved_notes = [note['name'] for note in self.notes if note['is_dirty']]
        if not unsaved_notes:
            event.accept()
            return
        reply = QMessageBox.question(
            self,
            'Save Changes?',
            f"You have unsaved changes in:\n\n{', '.join(unsaved_notes)}\n\nExit without saving?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Note", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self.new_note)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Note...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_note)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Note", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_note)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Note As...", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self.save_note_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        export_pdf_action = QAction("Export as PDF...", self)
        export_pdf_action.setShortcut("Ctrl+P")
        export_pdf_action.triggered.connect(self.export_pdf)
        file_menu.addAction(export_pdf_action)

        file_menu.addSeparator()

        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        note_menu = menu_bar.addMenu("&Note")
        rename_action = QAction("Rename Note", self)
        rename_action.setShortcut("F2")
        rename_action.triggered.connect(self.rename_note)
        note_menu.addAction(rename_action)

        close_action = QAction("Close Note", self)
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(self.close_current_note)
        note_menu.addAction(close_action)

        view_menu = menu_bar.addMenu("&View")
        
        toggle_preview_action = QAction("Toggle Preview", self)
        toggle_preview_action.setShortcut("Ctrl+T")
        toggle_preview_action.triggered.connect(self.toggle_preview_pane)
        view_menu.addAction(toggle_preview_action)

        view_menu.addSeparator()

        toggle_theme_action = QAction("Toggle Theme", self)
        toggle_theme_action.setShortcut("Ctrl+L")
        toggle_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(toggle_theme_action)

    def toggle_preview_pane(self):
        editor, preview = self._get_current_widgets()
        if preview:
            preview.setVisible(not preview.isVisible())

    def toggle_theme(self):
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.apply_stylesheet()
        for note in self.notes:
            if 'highlighter' in note:
                note['highlighter'].rehighlight() 

    def _create_status_bar(self):
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready")

    def apply_stylesheet(self):
        try:
            with open(f"style_{self.current_theme}.qss", "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.apply_stylesheet()
    window.show()
    sys.exit(app.exec())
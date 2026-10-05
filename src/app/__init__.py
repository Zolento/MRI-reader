"""
Application-layer services for :class:`src.main_window.MainWindow`.

``MainWindow`` stays a thin coordinator (layout, menus, signals); the logic
lives in these collaborators:

* :class:`~src.app.file_loader.FileLoader` - file dialogs and loading
* :class:`~src.app.display.DisplayController` - view extraction, coil
  combination, rendering and the bounded plane cache
* :class:`~src.app.enhancement.EnhancementController` - the two processors and
  the Image / K-Space target switching
"""

from .display import DisplayController
from .enhancement import EnhancementController
from .file_loader import FileLoader

__all__ = ["DisplayController", "EnhancementController", "FileLoader"]

import pyglet as pg
from core.math import Rect

class Widget(object):
    """Base class for all widgets"""
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.name = kwargs.get("name", "")
        self.parent = kwargs.get("parent", None)

        # -- position attributes
        self._x = kwargs.get('x', 0)
        self._y = kwargs.get('y', 0)

        self._gx = self._x
        self._gy = self._y

        # -- size attributes
        self._w = kwargs.get('w', 1)
        self._h = kwargs.get('h', 1)

        # -- layout attributes
        self._rect = Rect(0, 0, 1, 1)

        # -- draw attributes
        self._batch = kwargs.get('batch', pg.graphics.Batch())
        self._group = kwargs.get('group', pg.graphics.OrderedGroup(0))

        self._dirty = True
        self.shapes = dict()
        self.elements = dict()

    def _get_x(self):
        return self._x
    def _set_x(self, val):
        self._x = val
        self._dirty = True
    x = property(_get_x, _set_x)

    def _get_y(self):
        return self._y
    def _set_y(self, val):
        self._y = val
        self._dirty = True
    y = property(_get_y, _set_y)
    position = property(lambda self: (self._x, self._y))

    def _get_w(self):
        return self._w
    def _set_w(self, val):
        self._w = val
        self._dirty = True
    w = property(_get_w, _set_w)

    def _get_h(self):
        return self._h
    def _set_h(self, val):
        self._h = val
        self._dirty = True
    h = property(_get_h, _set_h)
    size = property(lambda self: (self._w, self._h))

    def _get_batch(self):
        return self._batch
    batch = property(_get_batch)

    def _get_group(self):
        return self._group
    group = property(_get_group)

    def _find_root(self):
        root = self
        while root.parent:
            root = root.parent
        return root

    def update_layout(self):
        self._dirty = False

    def update_batch(self, batch, group):
        for idx, shape in enumerate(self.shapes.values()):
            shape.update(batch, pg.graphics.OrderedGroup(idx, group))

        for idx, elem in enumerate(self.elements.values()):
            elem.update(batch, pg.graphics.OrderedGroup(idx, group))

    def hit_test(self, x, y):
        return self._rect.hit(x, y)

    def on_draw(self):
        return NotImplementedError()

    def on_update(self, dt):
        return NotImplementedError()

    def on_resize(self, *args):
        return NotImplementedError()

    def on_key_press(self, *args):
        return NotImplementedError()

    def on_key_release(self, *args):
        return NotImplementedError()

    def on_mouse_press(self, *args):
        return NotImplementedError()

    def on_mouse_release(self, *args):
        return NotImplementedError()

    def on_mouse_drag(self, *args):
        return NotImplementedError()

    def on_mouse_motion(self, *args):
        return NotImplementedError()

    def on_mouse_scroll(self, *args):
        return NotImplementedError()

    def on_text(self, *args):
        return NotImplementedError()

    def on_text_motion(self, *args):
        return NotImplementedError()

    def on_text_motion_select(self, *args):
        return NotImplementedError()

#  Copyright 2019 Ian Karanja <karanjaichungwa@gmail.com
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

import os
import pickle
import operator
import pyglet as pg
from pyglet.gl import *
from contextlib import contextmanager

from core.math import clamp
from core.app import Application
from resources import LevelData, Resources, sorted_levels
from core.utils import (
    set_flag,
    draw_path,
    draw_line,
    draw_point,
    image_set_size,
    mouse_over_rect,
    image_set_anchor_center,
)


class Editor:
    def __init__(self):
        self.levels = Resources.instance.levels()
        self.current = sorted_levels(0) if len(self.levels) else None
        self.data = dict()
        self.load()

    def load(self):
        if self.current:
            # -- load current leveldata
            for key, val in self.levels[self.current]._asdict().items():
                self.data[key] = val

        self.topbar = EditorTopbar(self.levels)
        self.toolbar = EditorToolbar(self.data)
        self.viewport = EditorViewport(self.data)

        # -- hook events
        self.topbar.new_btn.on_click(self.new)
        self.topbar.save_btn.on_click(self.save)

    def new(self):
        # -- create new level file
        new_level = Resources.instance.level(f"level_{len(self.levels)+1}")
        self.levels = Resources.instance.levels()

        # -- set as current level
        self.current = list(self.levels)[-1]
        for key, val in self.levels[self.current]._asdict().items():
            self.data[key] = val

        self.topbar.add_tab(self.current)
        self.toolbar = EditorToolbar(self.data)
        self.viewport = EditorViewport(self.data)

    def save(self):
        # -- remove temp data from self.data
        tmp_items = [key for key, v in self.data.items() if key.startswith("_")]
        tmp_data = [v for key, v in self.data.items() if key.startswith("_")]
        for it in tmp_items:
            del self.data[it]

        # -- save data
        ldata = LevelData(**self.data)
        f = open(self.current, "wb")
        pickle.dump(ldata, f)

        # -- restore temp data from self.data
        for key, val in zip(tmp_items, tmp_data):
            self.data[key] = val

        # # --  update viewport
        self.viewport.reload(self.data)
        print("Saved -- > ", self.current)

    def __iter__(self):
        return iter([self.viewport, self.toolbar, self.topbar])

    def _iter_call_meth(self, meth, *args, **kwargs):
        for obj in self:
            if hasattr(obj, meth):
                caller = operator.methodcaller(meth, *args, **kwargs)
                caller(obj)

    def on_draw(self):
        self._iter_call_meth("on_draw")

    def on_update(self, dt):
        self._iter_call_meth("on_update", dt)

        # -- check selected tab in topbar
        if self.topbar.tab_switched:
            self.current = sorted_levels(self.topbar.active_level)
            self.data.clear()

            # -- change level
            for key, val in self.levels[self.current]._asdict().items():
                self.data[key] = val

            self.topbar.tab_switched = False

        # -- update tools for viewport transform
        for tool in self.toolbar.tools:
            tool.set_viewport_transform(self.viewport.get_transform())

    def on_resize(self, *args):
        self._iter_call_meth("on_resize", *args)

    def on_key_press(self, *args):
        self._iter_call_meth("on_key_press", *args)

    def on_key_release(self, *args):
        self._iter_call_meth("on_key_release", *args)

    def on_mouse_press(self, *args):
        self._iter_call_meth("on_mouse_press", *args)

    def on_mouse_release(self, *args):
        self._iter_call_meth("on_mouse_release", *args)

    def on_mouse_drag(self, *args):
        self._iter_call_meth("on_mouse_drag", *args)

    def on_mouse_motion(self, *args):
        self._iter_call_meth("on_mouse_motion", *args)

    def on_mouse_scroll(self, *args):
        self._iter_call_meth("on_mouse_scroll", *args)

    def on_text(self, *args):
        self._iter_call_meth("on_text", *args)

    def on_text_motion(self, *args):
        self._iter_call_meth("on_text_motion", *args)

    def on_text_motion_select(self, *args):
        self._iter_call_meth("on_text_motion_select", *args)



class EditorTopbar:
    HEIGHT = 40

    def __init__(self, levels):
        self.levels = levels
        self.active_level = 0

        # -- topbar background
        self.topbar_settings = {
            "size": (Application.instance.window.width, self.HEIGHT),
            "color": (207, 188, 188, 255),
        }
        self.topbar = pg.image.SolidColorImagePattern(self.topbar_settings.get("color"))
        self.topbar_image = self.topbar.create_image(*self.topbar_settings.get("size"))

        # -- action buttons
        # -- images are 22x22, Toolbar width = 60
        hw = EditorToolbar.WIDTH / 2
        self.new_btn = ImageButton(
            "new", (hw / 2, Application.instance.window.height - self.HEIGHT / 2)
        )
        self.save_btn = ImageButton(
            "save", (hw * 1.5, Application.instance.window.height - self.HEIGHT / 2)
        )

        # -- tab buttons
        self.max_tabs = 4
        self.tabs_batch = pg.graphics.Batch()
        self.inactive_color = (50, 50, 50, 200)
        self.tabs = [
            TextButton(
                os.path.basename(level),
                bold=False,
                font_size=14,
                color=self.inactive_color,
                anchor_x="center",
                anchor_y="center",
                batch=self.tabs_batch,
            )
            for idx, level in enumerate(sorted_levels())
        ]

        if self.tabs:
            self.tabs[self.active_level].bold = True
            self.init_tabs()
            for tab in self.tabs:
                tab.on_click(self.switch_level, tab.text)

        # - tab switching flags
        self.tab_switched = False

    def get_rect(self):
        width = Application.instance.window.width - EditorToolbar.WIDTH
        size = (width, self.HEIGHT)
        center = (
            width / 2 + EditorToolbar.WIDTH,
            Application.instance.window.height - self.HEIGHT / 2,
        )
        return [center, size]

    def switch_level(self, level_txt):
        self.tab_switched = True
        for idx, level in enumerate(sorted_levels()):
            if os.path.basename(level) == level_txt:
                self.active_level = idx
                break

        # -- set clicked tab to bold
        for idx, tab in enumerate(self.tabs):
            if idx == self.active_level:
                tab.bold = True
            else:
                tab.bold = False

    def add_tab(self, level):
        # -- update list of levels from resources
        self.levels = Resources.instance.levels()
        # -- add a new tab and set as active
        ntab = TextButton(
            os.path.basename(level),
            bold=False,
            font_size=14,
            color=self.inactive_color,
            anchor_x="center",
            anchor_y="center",
            batch=self.tabs_batch,
        )
        ntab.on_click(self.switch_level, ntab.text)
        self.tabs.append(ntab)

        self.active_level = len(self.tabs) - 1
        self.switch_level(ntab.text)
        self.init_tabs()

    def init_tabs(self, _range=None):
        w = 110
        margin = 15
        start_x = EditorToolbar.WIDTH

        update = lambda tab: 0 if len(tab.text) == 13 else 5
        if _range is not None:
            for idx, tab in enumerate(map(lambda i: self.tabs[i], _range)):
                margin += update(tab)
                tab.x = start_x + (w / 2) + (idx * w) + ((idx + 1) * margin)
                tab.y = Application.instance.window.height - self.HEIGHT / 2
        else:
            for idx, tab in enumerate(self.tabs):
                margin += update(tab)
                tab.x = start_x + (w / 2) + (idx * w) + ((idx + 1) * margin)
                tab.y = Application.instance.window.height - self.HEIGHT / 2

        # -- recalculate max_tabs based on tabs and Application.instance.window width
        bar_width = Application.instance.window.width - EditorToolbar.WIDTH
        tab_averge_width = sum([t.get_size()[0] + margin for t in self.tabs]) / len(
            self.tabs
        )
        self.max_tabs = int(bar_width / tab_averge_width)

    def on_draw(self):
        # -- draw background
        w, h = Application.instance.size
        self.topbar_image.blit(0, h - self.HEIGHT)
        draw_line(
            (0, h - self.HEIGHT),
            (w, h - self.HEIGHT),
            color=(0.1, 0.1, 0.1, 0.8),
            width=5,
        )

        # -- draw action buttons
        self.new_btn.draw()
        self.save_btn.draw()

        # -- draw tab buttons
        if len(self.tabs) <= self.max_tabs:
            self.tabs_batch.draw()
        else:
            if self.active_level < self.max_tabs:
                self.init_tabs()
                for i in range(self.max_tabs):
                    self.tabs[i].draw()
            else:
                st = max(0, self.active_level - int(self.max_tabs / 2))
                sp = min(len(self.tabs) - 1, self.active_level + int(self.max_tabs / 2))
                self.init_tabs(range(st, sp + 1, 1))
                for i in range(st, sp + 1, 1):
                    self.tabs[i].draw()

    def on_update(self, dt):
        pass

    def on_resize(self, w, h):
        if self.tabs:
            self.init_tabs()
        self.new_btn.update(EditorToolbar.WIDTH * 0.25, h - self.HEIGHT / 2)
        self.save_btn.update(EditorToolbar.WIDTH * 0.75, h - self.HEIGHT / 2)

        self.topbar_settings["size"] = (w, self.HEIGHT)
        self.topbar_image = self.topbar.create_image(*self.topbar_settings.get("size"))

    def on_mouse_scroll(self, x, y, sx, sy):
        if not mouse_over_rect((x, y), *self.get_rect()):
            return

        # -- update active level based on scroll
        self.active_level = clamp(self.active_level + sy, 0, len(self.tabs) - 1)
        self.switch_level(self.tabs[self.active_level].text)

    def on_mouse_motion(self, x, y, dx, dy):
        self.new_btn.on_mouse_motion(x, y, dx, dy)
        self.save_btn.on_mouse_motion(x, y, dx, dy)
        for tab in self.tabs:
            tab.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x, y, button, mod):
        self.new_btn.on_mouse_press(x, y, button, mod)
        self.save_btn.on_mouse_press(x, y, button, mod)
        for tab in self.tabs:
            tab.on_mouse_press(x, y, button, mod)



class EditorToolbar:
    WIDTH = 60

    def __init__(self, data):
        # -- toolbar
        self.toolbar_settings = {
            "size": (self.WIDTH, Application.instance.window.height),
            "color": (207, 188, 188, 255),
        }
        self.toolbar = pg.image.SolidColorImagePattern(
            self.toolbar_settings.get("color")
        )
        self.toolbar_image = self.toolbar.create_image(
            *self.toolbar_settings.get("size")
        )

        # -- tools
        self.tools = [
            AddTileTool(data),
            AddAgentTool(data),
            AddWaypointTool(data),
            ObjectivesTool(data),
        ]

        self.tool_start_loc = (
            0,
            Application.instance.window.height - EditorTopbar.HEIGHT,
        )
        self.tool_settings = {"size": (50, 50), "border": (5, 5), "anchor": (25, 25)}
        self.init_tools()

    def init_tools(self):
        locx, locy = self.tool_start_loc
        # -- rely on orderd dict
        sz, brd, anch = [val for key, val in self.tool_settings.items()]

        for idx, tool in enumerate(self.tools):
            locx = brd[0] + anch[0]
            locy -= brd[1] + (sz[1] if idx > 0 else 0) + (anch[1] if idx == 0 else 0)
            tool.position = (locx, locy)
            tool.size = self.tool_settings.get("size")

    def get_rect(self):
        center = (
            self.WIDTH / 2,
            (Application.instance.window.height - EditorTopbar.HEIGHT) / 2,
        )
        size = (self.WIDTH, Application.instance.window.height - EditorTopbar.HEIGHT)
        return [center, size]

    def __iter__(self):
        return iter(self.tools)

    def _iter_call_meth(self, method, *args, **kwargs):
        """ Call meth on this objects __iter__ """
        for obj in self:
            if hasattr(obj, method):
                f = operator.methodcaller(method, *args, **kwargs)
                f(obj)

    # XXX Event handlers
    def on_draw(self):
        self.toolbar_image.blit(0, -EditorTopbar.HEIGHT)
        self._iter_call_meth("on_draw_first")
        self._iter_call_meth("on_draw")
        self._iter_call_meth("on_draw_last")

    def on_update(self, dt):
        self._iter_call_meth("on_update", dt)

        for tool in self:
            if tool.activated:
                # -- set all tools as inactive
                set_flag("is_active", False, self.tools)
                set_flag("activated", False, self.tools)

                # -- activate current tool
                tool.is_active = True

    def on_resize(self, w, h):
        self._iter_call_meth("on_resize", w, h)

        self.tool_start_loc = (0, h - EditorTopbar.HEIGHT)
        self.init_tools()

        self.toolbar_settings["size"] = (self.WIDTH, h)
        self.toolbar_image = self.toolbar.create_image(
            *self.toolbar_settings.get("size")
        )

    def on_key_press(self, *args):
        self._iter_call_meth("on_key_press", *args)

    def on_key_release(self, *args):
        self._iter_call_meth("on_key_release", *args)

    def on_mouse_press(self, x, y, button, mod):
        self._iter_call_meth("on_mouse_press", x, y, button, mod)

        # -- deactivate all tools if click over empty toolbar area
        if button == pg.window.mouse.LEFT and mouse_over_rect((x, y), *self.get_rect()):
            # -- check if mouse was clicked over toolbar but not over a tool,
            if not any(
                [
                    mouse_over_rect((x, y), tool.position, tool.size)
                    for tool in self.tools
                ]
            ):
                # -- set all tools as inactive
                set_flag("is_active", False, self.tools)
                set_flag("activated", False, self.tools)

    def on_mouse_release(self, *args):
        self._iter_call_meth("on_mouse_release", *args)

    def on_mouse_drag(self, *args):
        self._iter_call_meth("on_mouse_drag", *args)

    def on_mouse_motion(self, *args):
        self._iter_call_meth("on_mouse_motion", *args)

    def on_mouse_scroll(self, *args):
        self._iter_call_meth("on_mouse_scroll", *args)

    def on_text(self, *args):
        self._iter_call_meth("on_text", *args)

    def on_text_motion(self, *args):
        self._iter_call_meth("on_text_motion", *args)

    def on_text_motion_select(self, *args):
        self._iter_call_meth("on_text_motion_select", *args)


class EditorViewport:
    LINE_WIDTH = 2
    OFFSET = (EditorToolbar.WIDTH + LINE_WIDTH, LINE_WIDTH)

    GRID_SIZE = 20000
    GRID_SPACING = 100

    def __init__(self, data):
        self.data = data

        # -- panning options
        self._is_panning = False
        self._pan_offset = (0, 0)

        # -- zoom ptions
        self._zoom = (1, 1)
        self._zoom_sensitivity = 0.1

        # -- map options
        self.wall_img = Resources.instance.sprite("wall")
        image_set_size(self.wall_img, self.GRID_SPACING, self.GRID_SPACING)

        self.floor_img = Resources.instance.sprite("floor")
        image_set_size(self.floor_img, self.GRID_SPACING, self.GRID_SPACING)

        # -- player options
        self.player_img = Resources.instance.sprite("hitman1_stand")
        image_set_size(
            self.player_img, self.GRID_SPACING * 0.75, self.GRID_SPACING * 0.75
        )
        image_set_anchor_center(self.player_img)

        # -- enemy options
        self.enemy_img = Resources.instance.sprite("robot1_stand")
        image_set_size(
            self.enemy_img, self.GRID_SPACING * 0.75, self.GRID_SPACING * 0.75
        )
        image_set_anchor_center(self.enemy_img)

        self.enemy_target = Resources.instance.sprite("enemy_target")
        image_set_size(self.enemy_target, *(EditorViewport.GRID_SPACING,) * 2)
        image_set_anchor_center(self.enemy_target)

    def reload(self, data):
        self.data = data
        self = EditorViewport(data)

    def get_rect(self):
        width = Application.instance.window.width - EditorToolbar.WIDTH
        height = Application.instance.window.height - EditorTopbar.HEIGHT
        size = (width, height)
        center = (width / 2 + EditorToolbar.WIDTH, height / 2)
        return [center, size]

    def get_transform(self):
        return (self._pan_offset, self._zoom)

    @contextmanager
    def _editor_do_pan(self):
        glPushMatrix()
        glTranslatef(*self._pan_offset, 0)
        yield
        glPopMatrix()

    @contextmanager
    def _editor_do_zoom(self):
        glPushMatrix()
        glScalef(*self._zoom, 1)
        yield
        glPopMatrix()

    def _editor_draw_grid(self):
        glLineWidth(self.LINE_WIDTH)
        glBegin(GL_LINES)
        for y in range(0, self.GRID_SIZE, self.GRID_SPACING):
            glColor4f(1, 1, 1, 1)

            # -- vertical lines
            if y == 0:
                glColor4f(0, 0, 1, 1)
            glVertex2f(y, 0)
            glVertex2f(y, self.GRID_SIZE)

            # -- horizontal lines
            if y == 0:
                glColor4f(1, 0, 0, 1)
            glVertex2f(0, y)
            glVertex2f(self.GRID_SIZE, y)

        glEnd()

    def _editor_draw_map(self):
        for y, row in enumerate(self.data["map"]):
            for x, data in enumerate(row):
                offx, offy = x * self.GRID_SPACING, y * self.GRID_SPACING
                if data == "#":
                    self.wall_img.blit(offx, offy, 0)
                elif data == " ":
                    self.floor_img.blit(offx, offy, 0)

    def _editor_draw_player(self):
        self.player_img.blit(*self.data["player"], 0)

    def _editor_draw_enemies(self):
        for pos in self.data["enemies"]:
            self.enemy_img.blit(*pos, 0)

    def _editor_draw_waypoints(self):
        # -- check if waypoint tool is active
        waypoint_tool = [t for t in EditorTool.tools if isinstance(t, AddWaypointTool)][
            -1
        ]
        if not waypoint_tool.is_active:
            return

        waypoints = self.data.get("waypoints")
        if waypoints:
            # -- check if we have active enemy
            enemy_id = self.data.get("_active_enemy")
            if enemy_id:
                # -- select waypoints for active enemy
                points = waypoints[enemy_id - 1]

                # -- draw active enemy
                self.enemy_target.blit(*self.data["enemies"][enemy_id - 1], 0)

                # -- draw waypoints
                draw_path(points, color=(0, 0, 1, 1))
                for point in points:
                    draw_point(point, color=(1, 1, 1, 1))

    def on_draw(self):
        if not self.data:
            return

        glPushMatrix()
        glTranslatef(*self.OFFSET, 1)
        with self._editor_do_pan():
            with self._editor_do_zoom():
                self._editor_draw_grid()
                self._editor_draw_map()
                self._editor_draw_player()
                self._editor_draw_enemies()
                self._editor_draw_waypoints()
        glPopMatrix()

    def on_update(self, dt):
        pass

    def on_mouse_drag(self, x, y, dx, dy, button, mod):
        if not mouse_over_rect((x, y), *self.get_rect()):
            return

        if button == pg.window.mouse.MIDDLE:
            self._is_panning = True
            px, py = self._pan_offset
            px = 0 if (px + dx) > 0 else px + dx
            py = 0 if (py + dy) > 0 else py + dy
            self._pan_offset = (px, py)
        else:
            self._is_panning = False

    def on_mouse_scroll(self, x, y, sx, sy):
        if not mouse_over_rect((x, y), *self.get_rect()):
            return

        _sum = lambda x, y, val: (x + val, y + val)
        if sy < 0:
            self._zoom = _sum(*self._zoom, -self._zoom_sensitivity)
        else:
            self._zoom = _sum(*self._zoom, self._zoom_sensitivity)

        # -- clamp zoom to (0.2, 10.0) and round to  d.p
        self._zoom = tuple(map(lambda x: clamp(x, 0.2, 10.0), self._zoom))
        self._zoom = tuple(map(lambda x: round(x, 1), self._zoom))


class EditorTool:

    tools = []

    def __new__(cls, *args, **kwargs):
        instance = object.__new__(cls)
        EditorTool.tools.append(instance)
        return instance

    def __init__(self, options, data):
        # -- options
        # -- e.g {'Add Player' : player_image, 'Add_Enemy' : enemy_image}
        self.options = options
        self.level_data = data

        self.position = (0, 0)
        self.size = (0, 0)

        # -- set image anchors to center:
        for _, img in self.options.items():
            image_set_anchor_center(img)

        self.default = list(options)[0]

        self.tool_background = Resources.instance.sprite("tool_background")
        image_set_anchor_center(self.tool_background)

        self.tool_indicator = Resources.instance.sprite("tool_indicator")
        image_set_anchor_center(self.tool_indicator)

        self.tool_active = Resources.instance.sprite("tool_select")
        image_set_anchor_center(self.tool_active)

        # -- flags to show optional tools
        self.mouse_down_duration = 0
        self.mouse_hold_duration = 0.5
        self.start_show_event = False
        self.show_options = False

        # -- flags for active state of the tool
        self.is_active = False
        self.activated = False

        # -- flag to track viewport transform
        self._viewport_pan = (0, 0)
        self._viewport_zoom = (1, 1)

    def set_viewport_transform(self, val):
        self._viewport_pan = val[0]
        self._viewport_zoom = val[1]

    def mouse_pos_to_viewport(self, x, y):
        # -- convert mouse position to viewport position
        # -- subtract editor offset
        ox, oy = EditorViewport.OFFSET
        px, py = x - ox, y - oy

        # -- transform viewport pan
        panx, pany = self._viewport_pan
        px, py = px - panx, py - pany

        # -- transform viewport scale
        zx, zy = self._viewport_zoom
        px, py = px * (1 / zx), py * (1 / zy)
        return px, py

    def mouse_pos_to_map(self, x, y):
        # -- convert mouse position to map array indices
        vx, vy = self.mouse_pos_to_viewport(x, y)
        gs = EditorViewport.GRID_SPACING
        return int(vx) // gs, int(vy) // gs

    def on_draw(self):
        # -- draw tool background
        self.tool_background.blit(*self.position)

        # -- draw default tool
        img = self.options[self.default]
        img.blit(*self.position)

        # -- draw tool indicator
        if len(self.options.items()) > 1:
            # -- draw small arror to indicate more than one option
            if not self.show_options:
                self.tool_indicator.blit(*self.position)

        # -- draw tool active
        if self.is_active:
            self.tool_active.blit(*self.position)

        # -- draw all tool option when mouse held down
        # -- this will be drawn a little off side
        if self.show_options and len(self.options.items()) > 1:
            offx = 50
            for idx, (name, image) in enumerate(self.options.items(), 1):
                px, py = self.position
                loc = (px + (idx * offx), py)
                self.tool_background.blit(*loc)
                image.blit(*loc)

    def on_update(self, dt):
        if self.start_show_event:
            self.mouse_down_duration += dt

            if self.mouse_down_duration >= self.mouse_hold_duration:
                self.show_options = True
                self.start_show_event = False
                self.mouse_down_duration = 0

    def on_mouse_press(self, x, y, button, mod):
        if button == pg.window.mouse.LEFT:
            if mouse_over_rect((x, y), self.position, self.size):
                self.start_show_event = True

    def on_mouse_release(self, x, y, button, mod):
        if button == pg.window.mouse.LEFT:
            if self.start_show_event or self.show_options:
                self.activated = True

            if self.start_show_event:
                self.start_show_event = False

            if self.show_options:
                # -- check if mouse was released over a tool option
                # --  set that tool as active
                offx = 50
                for idx, (name, image) in enumerate(self.options.items()):
                    idx += 1
                    px, py = self.position
                    loc = (px + (idx * offx), py)
                    if mouse_over_rect((x, y), loc, self.size):
                        self.default = list(self.options)[idx - 1]

                self.show_options = False



class AddTileTool(EditorTool):
    def __init__(self, data):
        opts = {
            "Wall": Resources.instance.sprite("tool_wall"),
            "Floor": Resources.instance.sprite("tool_floor"),
        }
        super().__init__(opts, data)

    def _map_add_tile(self, idx, idy, data):
        _map = self.level_data.get("map")

        # -- modifiy map list to accomodate new wall
        items_to_add = (idx + 1) - len(_map[0])
        rows_to_add = (idy + 1) - len(_map)
        len_rows = len(_map[0])

        # -- add new rows
        if rows_to_add:
            for i in range(rows_to_add):
                _map.append(["" for _ in range(len_rows)])

        # -- add new items
        if items_to_add:
            for row in _map:
                for _ in range(items_to_add):
                    row.append("")

        # -- set wall at target index
        _map[idy][idx] = data

    def _map_add_wall_at(self, idx, idy):
        _map = self.level_data.get("map")
        if _map:
            # -- ensure list contains data
            if idy < len(_map) and idx < len(_map[0]):
                _map[idy][idx] = "#"
            else:
                self._map_add_tile(idx, idy, "#")

    def _map_remove_wall_at(self, idx, idy):
        _map = self.level_data.get("map")
        if _map:
            # -- ensure list contains data
            if idy < len(_map) and idx < len(_map[0]):
                _map[idy][idx] = ""

    def _map_add_floor_at(self, idx, idy):
        _map = self.level_data.get("map")
        if _map:
            # -- ensure list contains data
            if idy < len(_map) and idx < len(_map[0]):
                _map[idy][idx] = " "
            else:
                self._map_add_tile(idx, idy, " ")

    def _map_remove_floor_at(self, idx, idy):
        _map = self.level_data.get("map")
        if _map:
            # -- ensure list contains data
            if idy < len(_map) and idx < len(_map[0]):
                _map[idy][idx] = ""

    def _do_add_tile(self, x, y, mod):
        # -- if we are showing tool options for other tools, return
        for tool in EditorTool.tools:
            if tool.show_options:
                return

        map_id = self.mouse_pos_to_map(x, y)
        if self.default == "Wall":
            if mod & pg.window.key.MOD_CTRL:
                self._map_remove_wall_at(*map_id)
            else:
                self._map_add_wall_at(*map_id)
        elif self.default == "Floor":
            if mod & pg.window.key.MOD_CTRL:
                self._map_remove_floor_at(*map_id)
            else:
                self._map_add_floor_at(*map_id)

    def on_mouse_press(self, x, y, button, mod):
        super().on_mouse_press(x, y, button, mod)
        if not self.is_active:
            return
        if x < EditorToolbar.WIDTH:
            return

        if button == pg.window.mouse.LEFT:
            self._do_add_tile(x, y, mod)

    def on_mouse_drag(self, x, y, dx, dy, button, mod):
        # super().on_mouse_drag(x, y, button, mod)
        if not self.is_active:
            return
        if x < EditorToolbar.WIDTH:
            return

        if button == pg.window.mouse.LEFT:
            self._do_add_tile(x, y, mod)



class AddAgentTool(EditorTool):
    def __init__(self, data):
        opts = {
            "Player": Resources.instance.sprite("tool_player"),
            "Enemy": Resources.instance.sprite("tool_enemy"),
        }
        super().__init__(opts, data)

    def on_mouse_press(self, x, y, button, mod):
        super().on_mouse_press(x, y, button, mod)

        # -- ensure tool is active
        if not self.is_active:
            return

        if x < EditorToolbar.WIDTH:
            return

        if button == pg.window.mouse.LEFT:
            px, py = self.mouse_pos_to_viewport(x, y)

            if self.default == "Player":
                self.level_data["player"] = (px, py)
            elif self.default == "Enemy":
                if mod & pg.window.key.MOD_CTRL:
                    enemies = self.level_data["enemies"]
                    waypoints = self.level_data["waypoints"]
                    for idx, en in enumerate(enemies):
                        if mouse_over_rect(
                            (px, py), en, (EditorViewport.GRID_SPACING * 0.75,) * 2
                        ):
                            self.level_data["enemies"].remove(en)
                            self.level_data["waypoints"].remove(waypoints[idx])
                else:
                    self.level_data["enemies"].append((px, py))
                    self.level_data["waypoints"].append([])


class AddWaypointTool(EditorTool):
    def __init__(self, data):
        opts = {"Waypoint": Resources.instance.sprite("tool_waypoint")}
        super().__init__(opts, data)

    def on_mouse_press(self, x, y, button, mod):
        super().on_mouse_press(x, y, button, mod)

        # -- ensure tool is active
        if not self.is_active:
            return

        # -- ensure mouse if over viewport
        if x < EditorToolbar.WIDTH:
            return

        # -- create waypoint
        px, py = self.mouse_pos_to_viewport(x, y)
        if button == pg.window.mouse.LEFT:
            # -- check if an enemy is selected
            enemy_id = self.level_data.get("_active_enemy")
            if enemy_id:
                # -- ensure waypoint list exist
                waypoints = self.level_data.get("waypoints")
                if not waypoints:
                    self.level_data["waypoints"] = []
                    waypoints = self.level_data["waypoints"]

                # -- check if waypoints exist for all enemies
                missing = len(self.level_data["enemies"]) > len(waypoints)
                if missing:
                    for _ in range(len(self.level_data["enemies"]) - len(waypoints)):
                        waypoints.append([])

                if mod & pg.window.key.MOD_CTRL:
                    # -- remove waypoint at mouse location
                    selected = None
                    for point in waypoints[enemy_id - 1]:
                        if mouse_over_rect((px, py), point, (10, 10)):
                            selected = point
                            break
                    if selected:
                        waypoints[enemy_id - 1].remove(selected)
                else:
                    # -- add mouse location to the selected enemy waypoints
                    waypoints[enemy_id - 1].append((px, py))

        # -- select enemy
        elif button == pg.window.mouse.RIGHT:
            if mod & pg.window.key.MOD_CTRL:
                if self.level_data.get("_active_enemy"):
                    del self.level_data["_active_enemy"]
            else:
                enemies = self.level_data["enemies"]
                for idx, en in enumerate(enemies):
                    if mouse_over_rect(
                        (px, py), en, (EditorViewport.GRID_SPACING * 0.75,) * 2
                    ):
                        self.level_data["_active_enemy"] = idx + 1


class ObjectivesTool(EditorTool):
    WIDTH = 400
    HEIGHT = 180

    def __init__(self, data):
        opts = {"Objectives": Resources.instance.sprite("tool_objectives")}
        super().__init__(opts, data)

        self.batch = pg.graphics.Batch()
        self.panel_offset = (EditorToolbar.WIDTH, 0)

        # panel background
        self.background_settings = {
            "size": (self.WIDTH, self.HEIGHT),
            "color": (150, 100, 100, 255),
        }
        self.background = pg.image.SolidColorImagePattern(
            self.background_settings.get("color")
        )
        self.background_image = self.background.create_image(
            *self.background_settings.get("size")
        )

        # panel labels
        pad = 5
        left, top = EditorToolbar.WIDTH + pad, self.HEIGHT - pad

        self.labels = [
            pg.text.Label(
                "Level Name",
                x=left,
                y=top - 10,
                bold=True,
                anchor_y="top",
                color=(0, 0, 0, 255),
                batch=self.batch,
            ),
            pg.text.Label(
                "Objectives",
                x=left,
                y=top - 50,
                bold=True,
                anchor_y="top",
                color=(0, 0, 0, 255),
                batch=self.batch,
            ),
        ]

        # panel inputs
        start_x = left + 100
        start_y = top - 30
        width = self.WIDTH - (3 * pad + 100)

        data = self.level_data or {
            "name": "Level Name",
            "objectives": [f"Objective {i+1}" for i in range(3)],
        }
        has_objectives = data.get("objectives", None)
        self.inputs = [
            TextInput(data.get("name"), start_x, start_y, width, self.batch),
            TextInput(
                data.get("objectives")[0], start_x, start_y - 40, width, self.batch
            ),
            TextInput(
                data.get("objectives")[1], start_x, start_y - 80, width, self.batch
            ),
            TextInput(
                data.get("objectives")[2], start_x, start_y - 120, width, self.batch
            ),
        ]

        self.text_cursor = Application.instance.window.get_system_mouse_cursor("text")
        self.focus = None
        self.set_focus(self.inputs[0])

    def set_focus(self, focus):
        if self.focus:
            self.focus.caret.visible = False
            self.focus.caret.mark = self.focus.caret.position = 0

        self.focus = focus
        if self.focus:
            self.focus.caret.visible = True
            self.focus.caret.mark = 0
            self.focus.caret.position = len(self.focus.document.text)

    def next_focus(self):
        idx = self.inputs.index(self.focus) + 1
        if idx > len(self.inputs) - 1:
            idx = 0
        self.set_focus(self.inputs[idx])

    def save_data(self):
        self.level_data["name"] = self.inputs[0].document.text
        self.level_data["objectives"] = [inp.document.text for inp in self.inputs[1:]]

    def on_draw(self):
        super().on_draw()
        if self.is_active and self.level_data:
            self.background_image.blit(*self.panel_offset)
            self.batch.draw()

    def on_key_press(self, symbol, mod):
        if self.is_active and self.level_data:
            if symbol == pg.window.key.TAB:
                self.next_focus()
            elif symbol == pg.window.key.RETURN:
                self.save_data()
                self.next_focus()

    def on_mouse_motion(self, x, y, dx, dy):
        if self.is_active and self.level_data:
            for inp in self.inputs:
                if inp.hit_test(x, y):
                    Application.instance.window.set_mouse_cursor(self.text_cursor)
            else:
                Application.instance.window.set_mouse_cursor(None)

    def on_mouse_press(self, x, y, button, mod):
        super().on_mouse_press(x, y, button, mod)
        if self.is_active and self.level_data:
            for inp in self.inputs:
                if inp.hit_test(x, y):
                    self.set_focus(inp)
                    break
            else:
                self.set_focus(None)

            if self.focus:
                self.focus.caret.on_mouse_press(x, y, button, mod)

    def on_mouse_drag(self, *args):
        if self.is_active and self.level_data:
            if self.focus:
                self.focus.caret.on_mouse_drag(*args)

    def on_text(self, *args):
        if self.is_active and self.level_data:
            if self.focus:
                if "\r" not in args:
                    self.focus.caret.on_text(*args)
            self.save_data()

    def on_text_motion(self, *args):
        if self.is_active and self.level_data:
            if self.focus:
                self.focus.caret.on_text_motion(*args)

    def on_text_motion_select(self, *args):
        if self.is_active and self.level_data:
            if self.focus:
                self.focus.caret.on_text_motion_select(*args)


class TextInput:
    def __init__(self, text, x, y, width, batch=None):
        self.batch = batch

        self.document = pg.text.document.UnformattedDocument(text)
        self.document.set_style(0, len(self.document.text), dict(color=(0, 0, 0, 255)))
        font = self.document.get_font()
        height = font.ascent - font.descent

        self.layout = pg.text.layout.IncrementalTextLayout(
            self.document, width, height, multiline=False, batch=self.batch
        )
        self.caret = pg.text.caret.Caret(self.layout)

        self.layout.x = x
        self.layout.y = y

        # Rectangular outline
        pad = 2
        self.add_background(x - pad, y - pad, x + width + pad, y + height + pad)

    def hit_test(self, x, y):
        return (
            0 < x - self.layout.x < self.layout.width
            and 0 < y - self.layout.y < self.layout.height
        )

    def add_background(self, x1, y1, x2, y2):
        vert_list = self.batch.add(
            4,
            pg.gl.GL_QUADS,
            None,
            ("v2i", [x1, y1, x2, y1, x2, y2, x1, y2]),
            ("c4B", [200, 200, 220, 255] * 4),
        )


class Button(object):
    def __init__(self):
        self._callback = None
        self._callback_args = ()

    def on_click(self, action, *args):
        if callable(action):
            self._callback = action
            self._callback_args = args

    def hover(self, x, y):
        return NotImplementedError()

    def on_mouse_motion(self, x, y, dx, dy):
        self.hover(x, y)

    def on_mouse_press(self, x, y, button, mod):
        if button == pg.window.mouse.LEFT:
            if self.hover(x, y):
                self._callback(*self._callback_args)


class TextButton(pg.text.Label, Button):
    def __init__(self, *args, **kwargs):
        pg.text.Label.__init__(self, *args, **kwargs)
        Button.__init__(self)

        self._start_color = self.color
        self._hover_color = (200, 0, 0, 255)

    def _set_hcolor(self, val):
        self._hover_color = val

    hover_color = property(fset=_set_hcolor)

    def get_size(self):
        return self.content_width, self.content_height

    def hover(self, x, y):
        center = self.x, self.y
        if mouse_over_rect((x, y), center, self.get_size()):
            self.color = self._hover_color
            return True

        self.color = self._start_color
        return False


class ImageButton(Button):
    def __init__(self, image, position):
        Button.__init__(self)
        self.image = Resources.instance.sprite(image)
        image_set_anchor_center(self.image)

        self.x, self.y = position
        self.sprite = pg.sprite.Sprite(self.image, x=self.x, y=self.y)

    def update(self, px, py):
        self.x, self.y = px, py
        self.sprite.update(x=px, y=py)

    def hover(self, x, y):
        center = self.x, self.y
        size = self.sprite.width, self.sprite.height

        if mouse_over_rect((x, y), center, size):
            return True
        return False

    def draw(self):
        self.sprite.draw()


"""
============================================================
---   MAIN
============================================================
"""


def main():
    res = Resources()
    app = Application((800, 600), "Editor", resizable=True)
    app.process(Editor())
    app.run()


if __name__ == "__main__":
    main()

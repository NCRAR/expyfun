"""Hardware interfaces for key- and button-presses and mouse clicks"""

# Authors: Dan McCloy <drmccloy@uw.edu>
#          Eric Larson <larsoner@uw.edu>
#          Ross Maddox <rkmaddox@uw.edu>
#
# License: BSD (3-clause)

import numpy as np
from functools import partial
import pyglet
from pyglet.window import mouse

from ._utils import wait_secs, clock, string_types


class Keyboard(object):
    """Retrieve presses from various devices.

    Public metohds:
        __init__
        listen_presses
        get_presses
        wait_one_press
        wait_for_presses
        check_force_quit

    Methods to override by subclasses:
        _get_timebase
        _clear_events
        _retrieve_events
    """

    def __init__(self, ec, force_quit_keys):
        self.master_clock = ec._master_clock
        self.log_presses = ec._log_presses
        self.force_quit_keys = force_quit_keys
        self.listen_start = None
        ec._time_correction_fxns['keypress'] = self._get_timebase
        self.get_time_corr = partial(ec._get_time_correction, 'keypress')
        self.time_correction = self.get_time_corr()
        self.win = ec._win
        # always init pyglet response handler for error (and non-error) keys
        self.win.on_key_press = self._on_pyglet_keypress
        self._keyboard_buffer = []

    ###########################################################################
    # Methods to be overridden by subclasses
    def _clear_events(self):
        self._clear_keyboard_events()

    def _retrieve_events(self, live_keys):
        return self._retrieve_keyboard_events(live_keys)

    def _get_timebase(self):
        """Get keyboard time reference (in seconds)
        """
        return clock()

    def _clear_keyboard_events(self):
        self.win.dispatch_events()
        self._keyboard_buffer = []

    def _retrieve_keyboard_events(self, live_keys):
        # add escape keys
        if live_keys is not None:
            live_keys = [str(x) for x in live_keys]  # accept ints
            live_keys.extend(self.force_quit_keys)
        self.win.dispatch_events()  # pump events on pyglet windows
        targets = []
        for key in self._keyboard_buffer:
            if live_keys is None or key[0] in live_keys:
                targets.append(key)
        return targets

    def _on_pyglet_keypress(self, symbol, modifiers, emulated=False):
        """Handler for on_key_press pyglet events"""
        key_time = clock()
        if emulated:
            this_key = str(symbol)
        else:
            this_key = pyglet.window.key.symbol_string(symbol).lower()
            this_key = this_key.lstrip('_').lstrip('NUM_')
        self._keyboard_buffer.append((this_key, key_time))

    def listen_presses(self):
        """Start listening for keypresses.
        """
        self.time_correction = self.get_time_corr()
        self.listen_start = self.master_clock()
        self._clear_events()

    def get_presses(self, live_keys, timestamp, relative_to):
        """Get the current entire keyboard / button box buffer.
        """
        pressed = []
        if timestamp and relative_to is None:
            if self.listen_start is None:
                raise ValueError('I cannot timestamp: relative_to is None and '
                                 'you have not yet called listen_presses.')
            else:
                relative_to = self.listen_start
        pressed = self._retrieve_events(live_keys)
        return self._correct_presses(pressed, timestamp, relative_to)

    def wait_one_press(self, max_wait, min_wait, live_keys,
                       timestamp, relative_to):
        """Returns only the first button pressed after min_wait.
        """
        relative_to, start_time = self._init_wait_press(max_wait, min_wait,
                                                        live_keys, timestamp,
                                                        relative_to)
        pressed = []
        while (not len(pressed) and
               self.master_clock() - start_time < max_wait):
            pressed = self._retrieve_events(live_keys)

        # handle non-presses
        if len(pressed):
            pressed = self._correct_presses(pressed, timestamp, relative_to)[0]
        elif timestamp:
            pressed = (None, None)
        else:
            pressed = None
        return pressed

    def wait_for_presses(self, max_wait, min_wait, live_keys,
                         timestamp, relative_to):
        """Returns all button presses between min_wait and max_wait.
        """
        relative_to, start_time = self._init_wait_press(max_wait, min_wait,
                                                        live_keys, timestamp,
                                                        relative_to)
        pressed = []
        while (self.master_clock() - start_time < max_wait):
            pressed = self._retrieve_events(live_keys)
        return self._correct_presses(pressed, timestamp, relative_to)

    def check_force_quit(self, keys=None):
        """Compare key buffer to list of force-quit keys and quit if matched.

        This function always uses the keyboard, so is part of abstraction.
        """
        if keys is None:
            # only grab the force-quit keys
            keys = self._retrieve_keyboard_events([])
        else:
            if isinstance(keys, string_types):
                keys = [keys]
            if isinstance(keys, list):
                keys = [k for k in keys if k in self.force_quit_keys]
            else:
                raise TypeError('Force quit checking requires a string or '
                                ' list of strings, not a {}.'
                                ''.format(type(keys)))
        if len(keys):
            raise RuntimeError('Quit key pressed')

    def _correct_presses(self, pressed, timestamp, relative_to):
        """Correct timing of presses and check for quit press"""
        if len(pressed):
            pressed = [(k, s + self.time_correction) for k, s in pressed]
            self.log_presses(pressed)
            keys = [k for k, _ in pressed]
            self.check_force_quit(keys)
            if timestamp:
                pressed = [(k, s - relative_to) for k, s in pressed]
            else:
                pressed = keys
        return pressed

    def _init_wait_press(self, max_wait, min_wait, live_keys, timestamp,
                         relative_to):
        """Actions common to ``wait_one_press`` and ``wait_for_presses``
        """
        if np.isinf(max_wait) and live_keys == []:
            raise ValueError('max_wait cannot be infinite if there are no live'
                             ' keys.')
        if not min_wait <= max_wait:
            raise ValueError('min_wait must be less than max_wait')
        start_time = self.master_clock()
        if timestamp and relative_to is None:
            relative_to = start_time
        wait_secs(min_wait)
        self.check_force_quit()
        self._clear_events()
        return relative_to, start_time


#class Mouse(object):
#    """Class to track mouse properties and events
#
#    Parameters
#    ----------
#    win : instance of pyglet Window
#        The window the mouse is attached to.
#    visible : bool
#        Initial mouse visibility.
#    """
#    def __init__(self, window, visible=False):
#        self._visible = visible
#        self.win = window
#        self.set_visible(visible)
#
#    def set_visible(self, visible):
#        """Sets the visibility of the mouse
#
#        Parameters
#        ----------
#        visible : bool
#            If True, make mouse visible.
#        """
#        self.win.set_mouse_visible(visible)
#        self._visible = visible
#
#    @property
#    def visible(self):
#        """Mouse visibility"""
#        return self._visible
#
#    @property
#    def pos(self):
#        """The current position of the mouse in normalized units"""
#        x = (self.win._mouse_x - self.win.width / 2.) / (self.win.width / 2.)
#        y = (self.win._mouse_y - self.win.height / 2.) / (self.win.height / 2.)
#        return np.array([x, y])
#
#    @property
#    def buttons(self):
#        """The current press status of the mouse buttons"""
#        # 0 is left, 1 is middle, 2 is right
#        return np.where(self.win._mouse_buttons[1:])[0]


class Mouse(object):
    """Class to track mouse properties and events

    Parameters
    ----------
    win : instance of pyglet Window
        The window the mouse is attached to.
    visible : bool
        Initial mouse visibility.

    Public metohds:
        __init__
        listen_clicks
        get_clicks
        wait_one_click
        wait_for_clicks

    Methods to override by subclasses:
        _get_timebase
        _clear_events
        _retrieve_events
    """

    def __init__(self, ec, visible=False):
        self._visible = visible
        self.win = ec._win
        self.set_visible(visible)
        self.master_clock = ec._master_clock
        self.log_clicks = ec._log_clicks
        self.listen_start = None
        ec._time_correction_fxns['mouseclick'] = self._get_timebase
        self.get_time_corr = partial(ec._get_time_correction, 'mouseclick')
        self.time_correction = self.get_time_corr()
        self.win = ec._win
        self._check_force_quit = ec.check_force_quit
        self.win.on_mouse_press = self._on_pyglet_mouse_click
        self._mouse_buffer = []
        self._button_names = {mouse.LEFT: 'left', mouse.MIDDLE: 'middle',
                              mouse.RIGHT: 'right'}
        self._button_ids = {'left': mouse.LEFT, 'middle': mouse.MIDDLE,
                            'right': mouse.RIGHT}

    def set_visible(self, visible):
        """Sets the visibility of the mouse

        Parameters
        ----------
        visible : bool
            If True, make mouse visible.
        """
        self.win.set_mouse_visible(visible)
        self._visible = visible

    @property
    def visible(self):
        """Mouse visibility"""
        return self._visible

    @property
    def pos(self):
        """The current position of the mouse in normalized units"""
        x = (self.win._mouse_x - self.win.width / 2.) / (self.win.width / 2.)
        y = (self.win._mouse_y - self.win.height / 2.) / (self.win.height / 2.)
        return np.array([x, y])

    ###########################################################################
    # Methods to be overridden by subclasses
    def _clear_events(self):
        self._clear_mouse_events()

    def _retrieve_events(self, live_buttons):
        return self._retrieve_mouse_events(live_buttons)

    def _get_timebase(self):
        """Get mouse time reference (in seconds)
        """
        return clock()

    def _clear_mouse_events(self):
        self.win.dispatch_events()
        self._mouse_buffer = []

    def _retrieve_mouse_events(self, live_buttons):
        self.win.dispatch_events()  # pump events on pyglet windows
        targets = []
        for button in self._mouse_buffer:
            if live_buttons is None or button[0] in live_buttons:
                targets.append(button)
        return targets

    def _on_pyglet_mouse_click(self, x, y, button, modifiers):
        """Handler for on_mouse_press pyglet events"""
        button_time = clock()
        this_button = self._button_names[button]
        self._mouse_buffer.append((this_button, x, y, button_time))

    def listen_clicks(self):
        """Start listening for mouse clicks.
        """
        self.time_correction = self.get_time_corr()
        self.listen_start = self.master_clock()
        self._clear_events()

    def get_clicks(self, live_buttons, timestamp, relative_to):
        """Get the current entire mouse buffer.
        """
        clicked = []
        if timestamp and relative_to is None:
            if self.listen_start is None:
                raise ValueError('I cannot timestamp: relative_to is None and '
                                 'you have not yet called listen_clicks.')
            else:
                relative_to = self.listen_start
        clicked = self._retrieve_events(live_buttons)
        return self._correct_clicks(clicked, timestamp, relative_to)

    def wait_one_click(self, max_wait, min_wait, live_buttons,
                       timestamp, relative_to):
        """Returns only the first button clicked after min_wait.
        """
        relative_to, start_time = self._init_wait_click(max_wait, min_wait,
                                                        live_buttons,
                                                        timestamp,
                                                        relative_to)
        clicked = []
        while (not len(clicked) and
               self.master_clock() - start_time < max_wait):
            clicked = self._retrieve_events(live_buttons)

        # handle non-clicks
        if len(clicked):
            clicked = self._correct_clicks(clicked, timestamp, relative_to)[0]
        elif timestamp:
            clicked = (None, None)
        else:
            clicked = None
        return clicked

    def wait_for_clicks(self, max_wait, min_wait, live_buttons,
                        timestamp, relative_to):
        """Returns all clicks between min_wait and max_wait.
        """
        relative_to, start_time = self._init_wait_click(max_wait, min_wait,
                                                        live_buttons,
                                                        timestamp,
                                                        relative_to)
        clicked = []
        while (self.master_clock() - start_time < max_wait):
            clicked = self._retrieve_events(live_buttons)
        return self._correct_clicks(clicked, timestamp, relative_to)

    def _correct_clicks(self, clicked, timestamp, relative_to):
        """Correct timing of clicks"""
        if len(clicked):
            clicked = [(b, x, y, s + self.time_correction) for
                       b, x, y, s in clicked]
            self.log_clicks(clicked)
            buttons = [(b, x, y) for b, x, y, _ in clicked]
            self._check_force_quit()
            if timestamp:
                clicked = [(b, x, y, s - relative_to) for
                           b, x, y, s in clicked]
            else:
                clicked = buttons
        return clicked

    def _init_wait_click(self, max_wait, min_wait, live_buttons, timestamp,
                         relative_to):
        """Actions common to ``wait_one_click`` and ``wait_for_clicks``
        """
        if np.isinf(max_wait) and live_buttons == []:
            raise ValueError('max_wait cannot be infinite if there are no live'
                             ' mouse buttons.')
        if not min_wait <= max_wait:
            raise ValueError('min_wait must be less than max_wait')
        start_time = self.master_clock()
        if timestamp and relative_to is None:
            relative_to = start_time
        wait_secs(min_wait)
        self._check_force_quit()
        self._clear_events()
        return relative_to, start_time

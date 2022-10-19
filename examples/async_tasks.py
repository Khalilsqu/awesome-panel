"""# Introduction

When creating awesome analytics apps you sometimes wants to run jobs in the background or provide
streaming analytics to your users.

Panel also supports these use cases as its running on top of the asynchronous web server Tornado.

**Below we show case how to start a background thread that updates a progressbar while
the rest of the application remains responsive.**

This example is based on the discussion [Can I load data asynchronously in Panel?]\
(https://discourse.holoviz.org/t/can-i-load-data-asynchronously-in-panel/452).

If you really deep dive into this, then you can study
[tornado.ioloop.IOLoop](https://www.tornadoweb.org/en/stable/ioloop.html),
[concurrent.futures.ThreadPoolExecutor]\
(https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor),
[Panel.io.server.unlocked](https://panel.holoviz.org/api/panel.io.html#panel.io.server.unlocked)"""

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import numpy as np
import panel as pn
import param
from panel.io.server import unlocked
from tornado.ioloop import IOLoop

from awesome_panel import config


class ProgressExtMod(param.Parameterized):
    """A component for easy progress reporting"""

    completed = param.Integer(default=0)
    bar_color = param.String(default="info")
    num_tasks = param.Integer(default=100, bounds=(1, None))

    # @param.depends('completed', 'num_tasks')
    @property
    def value(self) -> int:
        """Returs the progress value

        Returns:
            int: The progress value
        """
        return int(100 * (self.completed / self.num_tasks))

    def reset(self):
        """Resets the value and message"""
        # Please note the order matters as the Widgets updates two times. One for each change
        self.completed = 0

    @param.depends("completed", "message", "bar_color")
    def view(self):
        """View the widget
        Returns:
            pn.viewable.Viewable: Add this to your app to see the progress reported
        """
        if self.value:
            return pn.widgets.Progress(
                active=True, value=self.value, align="center", sizing_mode="stretch_width"
            )
        return None

    @contextmanager
    def increment(self):
        """Increment the value
        Can be used as context manager or decorator?
        Yields:
            None: Nothing is yielded
        """
        self.completed += 1
        yield
        if self.completed == self.num_tasks:
            self.reset()


executor = ThreadPoolExecutor(max_workers=2)  # pylint: disable=consider-using-with
progress = ProgressExtMod()


class AsyncComponent(pn.viewable.Viewer):
    """An component that demonstrates how to setup use an asynchronous background task in Panel"""

    select = param.Selector(objects=range(10))
    slider = param.Number(2, bounds=(0, 10))
    text = param.String()

    do_stuff = param.Action(lambda self: self.do_calc(), label="START")
    result = param.Number(0)
    view = param.Parameter()

    def __init__(self, **params):
        super().__init__(**params)

        pn.config.sizing_mode = "stretch_width"

        self._layout = pn.Column(
            pn.pane.Markdown("## Background Task"),
            pn.Param(
                self,
                parameters=["do_stuff", "result"],
                widgets={"result": {"disabled": True}, "do_stuff": {"button_type": "primary"}},
                show_name=False,
            ),
            progress.view,
            pn.pane.Markdown("## Other Tasks"),
            pn.Param(
                self,
                parameters=["select", "slider", "text"],
                widgets={"text": {"disabled": True}},
                show_name=False,
            ),
        )

    def __panel__(self):
        return self._layout

    @param.depends("slider", "select", watch=True)
    def _on_slider_change(self):
        # This functions does some other python code which we want to keep responsive
        if self.select:
            select = self.select
        else:
            select = 0
        self.text = str(self.slider + select)

    def do_calc(self, num_tasks=10):
        """Runs background tasks num_tasks times"""
        num_tasks = 20
        progress.num_tasks = num_tasks
        loop = IOLoop.current()
        for _ in range(num_tasks):
            future = executor.submit(self._blocking_task)
            loop.add_future(future, self._update)

    @progress.increment()
    def _update(self, future):
        number = future.result()
        with unlocked():
            self.result += number

    @staticmethod
    def _blocking_task():
        time.sleep(np.random.randint(1, 2))
        return 5


if __name__.startswith("bokeh"):
    config.extension(url="async_tasks")

    pn.pane.Markdown(__doc__).servable()
    AsyncComponent().servable()  # pylint: disable=no-value-for-parameter

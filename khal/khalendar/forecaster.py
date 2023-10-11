'''
Created on 10 oct. 2023

@author: bde
'''


import logging
import re
from datetime import datetime, timedelta
from typing import Dict

from khal.khalendar.khalendar import CalendarCollection

logger = logging.getLogger('forecaster')


class ForecastedWeek:
    def __init__(self, date, collection, locale):
        self.remains = 5.0
        self.tasks = []
        self.old_forecast_events = []  # to delete before new event insertion
        self.all_day_events = []

        self.first_day = date - timedelta(days=date.weekday() % 7)
        self.last_day = self.first_day + timedelta(days=5)

        start_local = locale['local_timezone'].localize(self.first_day)
        end_local = locale['local_timezone'].localize(self.last_day)

        start = start_local.replace(tzinfo=None)
        end = end_local.replace(tzinfo=None)

        events = sorted(collection.get_localized(start_local, end_local))
        events_float = sorted(collection.get_floating(start, end))
        events = sorted(events + events_float)

        clock_regexp = re.compile(':clock1: ([0-9\\.]+)d')
        for event in events:
            if event.allday:
                if event.description().contains(':DO_NOT_EDIT:'):
                    self.old_forecast_events.append(event)
                else:
                    self.all_day_events.append(event)
                    clock_duration = 1.0
                    for line in event.description().splitlines():
                        match_res = clock_regexp.match(line)
                        if match_res:
                            clock_duration = float(match_res.group())
                            break
                    self.remains -= clock_duration

    def build_event_to_insert(self, calendar_name: str):
        # icalendar.new_vevent
        # try:
        #     event = collection.create_event_from_dict(event_args, calendar_name=calendar_name)
        # except ValueError as error:
        #     raise FatalError(error)

        return []

    def __repr__(self):
        return f'ForecastedWeek[remains: {self.remains}, '\
            + f'old_forecast_events: {self.old_forecast_events}, '\
            + f'all_day_events: {self.all_day_events}, '\
            + f'tasks: {self.tasks}]'


class ForecastedTask:
    # TODO: summary / url
    def __init__(self):
        self.since_date = datetime.now()
        self.since_week_nb = self.since_date.isocalendar().year * 100 \
            + self.since_date.isocalendar().week
        self.day_duration = 1.0
        self._repeat_per_week = None
        self.max_day = 1
        self.consumed = 0.0
        self.url = ""
        self.summary = "a forecasted task"
        self.float = False

    def load_from_json(self, task):
        self.since_date = datetime.strptime(task["since_date"], '%Y-%m-%d')
        self.since_week_nb = self.since_date.isocalendar().year * 100 \
            + self.since_date.isocalendar().week

        if "day_duration" in task:
            self.day_duration = float(task["day_duration"])

        if "float" in task:
            self.float = bool(task["float"])

        if "repeat_per_week" in task:
            self._repeat_per_week = int(task["repeat_per_week"])

        if "max" in task:
            self.max_day = int(task["max"])
        if "consumed" in task:
            self.consumed = float(task["consumed"])

        if "url" in task:
            self.url = task["url"]

        if "summary" in task:
            self.summary = task["summary"]

    def repeat_per_week(self):
        out = self._repeat_per_week
        if out is None:
            if self.float:
                # _repeat_per_week is not set and float is true ==> maximum repeat
                out = int(5.0/self.day_duration)
            else:
                out = 1.0  # default value
        return out

    def duration_per_week(self):
        out = 1.0
        if self._repeat_per_week is None:
            if self.float:
                # _repeat_per_week is not set and float is true
                # ==> minimize day duration to increase maximum repeat
                out = self.day_duration
            else:
                out = self.day_duration  # default value
        else:
            out = self._repeat_per_week*self.day_duration
        return out

    def __repr__(self):
        return f'ForecastedTask[summary: {self.summary}, '\
            + f'url: {self.url}, '\
            + f'duration: {self.day_duration}, '\
            + f'float: {self.float}, '\
            + f'repeat_per_week: {self._repeat_per_week}, '\
            + f'max_day: {self.max_day}, '\
            + f'consumed: {self.consumed}]'


class ForecastConfig:
    def __init__(self, data):
        self.forecasted_tasks = []
        if "forecasted_tasks" not in data:
            raise ValueError("Key 'forecasted_tasks' not found in loaded data!")
        for task in data["forecasted_tasks"]:
            t = ForecastedTask()
            t.load_from_json(task)
            self.forecasted_tasks.append(t)
        logger.debug('Forecast config read!')


class Forecaster:
    '''
    classdocs
    '''

    def __init__(self, collection: CalendarCollection, khal_conf, env):
        '''
        Constructor
        '''
        self.collection = collection
        self.khal_conf = khal_conf
        self.env = env
        self.forecast_conf = None
        self.weeks: Dict[str, ForecastedWeek] = {}

    def parse_config(self, config_data, start_date):
        self.forecast_conf = ForecastConfig(config_data)

        week_nb = start_date.isocalendar().year * 100 + start_date.isocalendar().week
        total_remain_days = 1
        while total_remain_days > 0:
            logger.warning("Week " + str(week_nb))
            total_remain_days = 0

            current_week = ForecastedWeek(start_date, self.collection, self.khal_conf['locale'])
            for task in self.forecast_conf.forecasted_tasks:

                if task.since_week_nb <= week_nb and task.max_day - task.consumed > 0 \
                        and current_week.remains >= task.duration_per_week():
                    for _ in range(0, task.repeat_per_week()):
                        forecasted_task = ForecastedTask()
                        forecasted_task.summary = task.summary
                        forecasted_task.url = task.url
                        forecasted_task.day_duration = task.day_duration
                        current_week.tasks.append(forecasted_task)

                        current_week.remains = current_week.remains - task.day_duration
                        if current_week.remains < task.day_duration:
                            break
                    task.consumed = task.consumed + task.duration_per_week()

                total_remain_days = total_remain_days + (task.max_day - task.consumed)

            logger.warning("  Total remain: " + str(total_remain_days))
            logger.warning("  Week remain: " + str(current_week.remains))
            for t in current_week.tasks:
                logger.warning("  planned: " + str(t))

            self.weeks[week_nb] = current_week
            start_date = start_date + timedelta(weeks=1)
            week_nb = start_date.isocalendar().year * 100 + start_date.isocalendar().week

        logger.warning("Fixed tasks:")
        for t in self.forecast_conf.forecasted_tasks:
            logger.warning("  task: " + str(t))

    def build_event_to_insert(self, calendar_name: str):
        out = []
        for week in self.weeks.values():
            out.append(week.build_event_to_insert(calendar_name))
        return out

    def event_to_delete(self):
        out = []
        for week in self.weeks.values():
            out = out + week.old_forecast_events
        return out

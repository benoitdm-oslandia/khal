'''
Created on 10 oct. 2023

@author: bde
'''


import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict

from khal.custom_types import EventCreationTypes
from khal.khalendar.khalendar import CalendarCollection

logger = logging.getLogger('forecaster')


class ForecastedWeek:
    '''
    Handle forecast week data: new/old tasks, time, etc.
    '''

    def __init__(self, date, collection, locale):
        self.remains = 5.0
        self.tasks = []
        self.old_forecast_events = []  # to delete before new event insertion
        self.all_day_events = []

        self.first_day = date - timedelta(days=date.weekday() % 7)
        self.last_day = self.first_day + timedelta(days=5)
        self.locale = locale

        start_local = self.locale['local_timezone'].localize(
            datetime.combine(self.first_day, datetime.min.time()))
        end_local = self.locale['local_timezone'].localize(
            datetime.combine(self.last_day, datetime.min.time()))

        start = start_local.replace(tzinfo=None)
        end = end_local.replace(tzinfo=None)

        events = sorted(collection.get_localized(start_local, end_local))
        events_float = sorted(collection.get_floating(start, end))
        events = sorted(events + events_float)

        # load already existing events (manually or forecasted)
        clock_regexp = re.compile(':clock1: ([0-9\\.]+)d')
        # logger.warning(f'Found event for week {self.first_day}: {len(events)}')
        for event in events:
            if event.allday:
                # logger.warning(f'event desc0: {event.description}')
                if type(event.description) is list:
                    desc = str(event.description[0])
                else:
                    desc = str(event.description)
                # logger.warning(f'event desc1: {desc}')
                if ':DO_NOT_EDIT:' in desc:
                    self.old_forecast_events.append(event)
                else:
                    clock_duration = 1.0
                    for line in desc.splitlines():
                        match_res = clock_regexp.search(line)
                        if match_res:
                            clock_duration = float(match_res.group(1))
                            break
                    task_from_event = ForecastedTask()
                    task_from_event.since_date = event.start_local
                    task_from_event.duration = clock_duration
                    self.all_day_events.append(task_from_event)
                    self.remains -= clock_duration

    def build_event_to_insert(self, calendar_name: str):
        '''
        Create event list according to existing events and new forecasted ones
        '''
        out: list[EventCreationTypes] = []

        def takeDuration(t: ForecastedTask):
            return t.day_duration

        def takeStartDate(t: ForecastedTask):
            return t.since_date

        # AllDayEventS clone
        ades = self.all_day_events.copy()
        # ForecastTaskS clone
        fts = self.tasks.copy()
        list.sort(ades, reverse=True, key=takeStartDate)
        list.sort(fts, reverse=True, key=takeDuration)

        # compute what remain per day according to existing task in calendar
        week_allocation: list[ForecastedTask] = []
        for day_idx in range(0, 5):
            day_date = self.first_day + timedelta(days=day_idx)

            t = ForecastedTask()
            t.since_date = day_date
            t.day_duration = 0.0

            for ade in ades:
                if ade.since_date == day_date:
                    t.day_duration += ade.day_duration

            week_allocation.append(t)

        # allocate task to available days
        while len(fts) > 0:
            for day in week_allocation:
                if day.day_duration + fts[0].day_duration <= 1.0:
                    # update day remaining duration
                    day.day_duration += fts[0].day_duration
                else:
                    # no room left today!
                    continue
                ft = fts.pop(0)

                desc = f'''
:clock1: {ft.day_duration}d
:DO_NOT_EDIT:
'''
                summary = f'AUTO 1/{int(1/ft.day_duration)} {ft.summary}'

                vevent = EventCreationTypes({
                    'location': None,
                    'categories': None,
                    'repeat': None,
                    'until': "",
                    'alarms': "",
                    'url': ft.url,
                    'summary': summary,
                    'allday': True,
                    'description': desc,
                    'dtstart': day.since_date,
                    'dtend': day.since_date + timedelta(days=1),
                    'timezone': self.locale['local_timezone'],
                })
                out.append(vevent)

                if len(fts) == 0:
                    break

        return out

    def __repr__(self):
        return f'ForecastedWeek[remains: {self.remains}, '\
            + f'old_forecast_events: {self.old_forecast_events}, '\
            + f'all_day_events: {self.all_day_events}, '\
            + f'tasks: {self.tasks}]'


class ForecastedTask:
    '''
    A forecasted task. Used to hold configuration data and new forecasted task
    '''

    def __init__(self):
        self.since_date = date.today()
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
        self.since_date = datetime.strptime(task["since_date"], '%Y-%m-%d').date()
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
    '''
    Create forecast input data from json config
    '''

    def __init__(self, json_data):
        self.forecasted_tasks = []
        if "forecasted_tasks" not in json_data:
            raise ValueError("Key 'forecasted_tasks' not found in loaded data!")
        for task in json_data["forecasted_tasks"]:
            t = ForecastedTask()
            t.load_from_json(task)
            self.forecasted_tasks.append(t)
        logger.debug('Forecast config read!')


class Forecaster:
    '''
    Try to forecast events in calendar by filling the week with event rules.
    These rules are defined in a separated json file.
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
        '''
        load configuration and forecast tasks
        '''
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
        '''
        Returns the list of new forecast events
        '''
        out = []
        for week in self.weeks.values():
            out += week.build_event_to_insert(calendar_name)
        return out

    def event_to_delete(self):
        '''
        Returns the list of previously forecast events
        '''
        out = []
        for week in self.weeks.values():
            out += week.old_forecast_events
        return out

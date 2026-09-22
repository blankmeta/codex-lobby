from codex_switch.domain.activity import label
from .activity import compact, elapsed
from .menu import Option, TerminalMenu, clipped


class SessionMenu:
    def __init__(self, app, console, menu=None):
        self.app, self.c = app, console
        self.menu = menu or TerminalMenu(console)

    def run(self):
        if self.app.sessions is None: return 0
        project_only = True
        while True:
            project = self.app.projects.current() if self.app.projects else None
            entries = self.app.sessions.list(project if project_only else None)
            options = [Option(s.key,clipped(s.title,56)+" · "+s.provider.capitalize(),(s.account,clipped(s.project,80))) for s in entries]
            options += [Option("scope",self.c.text("All projects" if project_only else "Current project", "Все проекты" if project_only else "Текущий проект")),Option("back",self.c.text("Back","Назад"))]
            key = self.menu.choose(self.c.text("Sessions · last 200","Сессии · последние 200"),options,
                                   context=(self.c.text("Local logs · no model requests","Локальные журналы · без запросов к модели"),))
            if key in (None,"back"): return 0
            if key == "scope": project_only = not project_only
            else: self.show(key)

    def show(self,key):
        sort = "calls"
        while True:
            report = self.app.sessions.analyze(key)
            usage = report.tokens
            rows = sorted(report.totals(),key=lambda r:(r[sort],r["calls"]),reverse=True)[:10]
            options = []
            for row in rows:
                options.append(Option(row["category"],f"{label(row['category'],self.c.ru):24} {row['calls']:>4}  {compact(row['tokens']) if row['model_steps'] else '—':>7}  {elapsed(row['seconds']) if row['timed_calls'] else '—':>6}",
                                      (self.c.text("Tokens belong to model requests, not individual commands.","Токены относятся к запросам модели, не к отдельным командам."),
                                       self.c.text(f"Repeated results: {row['repeats']} · errors: {row['errors']}",f"Повторные результаты: {row['repeats']} · ошибки: {row['errors']}"))))
            options += [Option("sort", self.c.text("Sort: ","Сортировка: ")+self.c.text(sort,{"calls":"вызовы","tokens":"токены","seconds":"время"}[sort])),
                        Option("refresh",self.c.text("Refresh","Обновить")),Option("back",self.c.text("Back","Назад"))]
            context = (self.c.text("Tokens: ","Токены: ")+compact(usage.total if usage else None)+self.c.text(" · including cache"," · включая кэш"),
                       self.c.text("Action                    Calls   Tokens    Time","Действие                  Вызовы  Токены   Время"))
            selected = self.menu.choose(clipped(report.title or "Session",70),options,context=context)
            if selected in (None,"back"): return
            if selected == "sort": sort = {"calls":"tokens","tokens":"seconds","seconds":"calls"}[sort]
            elif selected != "refresh": self.calls(report,selected)

    def calls(self,report,category):
        actions = [a for a in report.actions.values() if a.category == category]
        options = [Option(a.id,clipped(a.command or a.tool,70), (a.tool,clipped(a.result or self.c.text("No result recorded","Результат не записан"),160),
                           self.c.text("Time: ","Время: ")+elapsed(a.seconds))) for a in actions[-200:]]
        options.append(Option("back",self.c.text("Back","Назад")))
        while True:
            key = self.menu.choose(label(category,self.c.ru),options)
            if key in (None,"back"): return
            action = next(a for a in actions if a.id == key)
            details = [action.command or action.tool,action.result or self.c.text("No recorded result","Нет записанного результата")]
            lines = [line[i:i+72] for line in details for i in range(0,len(line),72)]
            self.menu.choose(self.c.text("Recorded call","Записанный вызов"),[Option(str(i),line) for i,line in enumerate(lines)]+[Option("back",self.c.text("Back","Назад"))])

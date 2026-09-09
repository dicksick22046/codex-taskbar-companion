import tempfile
import unittest
from pathlib import Path
from string import Formatter

from codex_taskbar.i18n import COPY, LANGUAGES, project_label, translate
from codex_taskbar.preferences import read_settings, write_settings


class LanguageTests(unittest.TestCase):
    def test_language_persists_without_changing_other_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            self.assertEqual(read_settings(path)['language'],'en')
            before={'show_week':False,'chart_unit':'100M','hover_panels':True,'notified_version':'0.2.4'}
            for language in (*LANGUAGES,'invalid'):
                write_settings(path,{**before,'language':language})
                loaded=read_settings(path)
                self.assertEqual(loaded['language'],language if language in LANGUAGES else 'en')
                self.assertTrue(all(loaded[key]==value for key,value in before.items()))

    def test_translations_preserve_all_format_fields(self):
        fields=lambda text:{name for _,name,_,_ in Formatter().parse(text) if name is not None}
        for english,chinese in COPY.items():
            with self.subTest(key=english):
                self.assertEqual(fields(english),fields(chinese))
                values=dict.fromkeys(fields(english),'123')
                for language in LANGUAGES:self.assertTrue(translate(language,english,**values))

    def test_only_missing_project_is_translated(self):
        self.assertEqual(project_label('','en'),'No project')
        self.assertEqual(project_label('','zh-CN'),'无项目')
        for name in ('无项目','No project','我的项目','Running'):
            for language in LANGUAGES:self.assertEqual(project_label(name,language),name)

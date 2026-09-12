import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
from PySide6.QtCore import Qt,QEvent,QRect
from PySide6.QtGui import QKeyEvent,QShowEvent,QHideEvent
from codex_taskbar import app
from codex_taskbar.codex_api import CodexApi
from codex_taskbar.provider import Provider
from codex_taskbar.task_finder import finder_rows,filter_rows,sort_rows,cell_text,TaskFinder
from tests import test_interactions as fixtures


class CatalogTests(unittest.TestCase):
    def test_unread_identity_request_does_not_refresh_credentials(self):
        api=CodexApi.__new__(CodexApi);api.call=Mock(return_value={'authMethod':None,'requiresOpenaiAuth':True})
        self.assertIsNone(api.unread_identity())
        api.call.assert_called_once_with('getAuthStatus',{'includeToken':True,'refreshToken':False})
    def test_explicit_sources_paginate_deduplicate_and_exclude_children(self):
        api=CodexApi.__new__(CodexApi)
        api.call=Mock(side_effect=[{'data':[]},{'data':[{'id':'a'},{'id':'child','parentThreadId':'a'}],'nextCursor':'next'},
                                   {'data':[{'id':'a'},{'id':'b'}],'nextCursor':None}])
        projects,rows=api.catalog();self.assertEqual([r['id'] for r in rows],['a','b'])
        for call in api.call.call_args_list[1:]:
            self.assertEqual(call.args[1]['sourceKinds'],['cli','vscode','appServer','exec'])
            self.assertTrue(call.args[1]['useStateDbOnly'])
        self.assertEqual(api.call.call_args_list[-1].args[1]['cursor'],'next')

    def test_full_catalog_is_memory_only(self):
        with tempfile.TemporaryDirectory() as folder:
            provider=Provider.__new__(Provider);provider.runtime_dir=Path(folder);provider.lock=threading.Lock()
            provider.snapshot={'tasks':[],'catalog':[{'id':'a','title':'Private task title'}]}
            provider._write_snapshot(force=True)
            self.assertIn('catalog',provider.get())
            self.assertNotIn('catalog',json.loads((Path(folder)/'snapshot.json').read_text()))

    def test_search_terms_project_and_order_use_metadata_without_inventing_states(self):
        data={'catalog':[{'id':'b','title':'Review 中文 API','project':'Alpha','updated_at':200},
                         {'id':'a','title':'Readme','project':'','updated_at':200},
                         {'id':'c','title':'Alpha migration','project':'Beta','updated_at':100}],
              'tasks':[{'id':'b','running':True,'project':'Alpha','title':'Review 中文 API'}]}
        rows=finder_rows(data,'en')
        self.assertEqual([r['id'] for r in rows],['a','b','c'])
        self.assertEqual([r['id'] for r in filter_rows(rows,'ALPHA 中文')],['b'])
        self.assertEqual([r['id'] for r in filter_rows(rows,'alpha','Beta')],['c'])
        self.assertEqual([r['id'] for r in filter_rows(rows,project='')],['a'])
        self.assertEqual(rows[0]['kind'],'');self.assertEqual(rows[1]['kind'],'running')


class FinderInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])

    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        saving=patch.object(self.bar,'save_settings');self.save=saving.start();self.addCleanup(saving.stop)
        self.data['tasks']=[];self.data['recent_tasks']=[]
        self.data['catalog']=[{'id':str(i),'title':f'Task {i}','project':'App' if i%2 else 'Docs','updated_at':1700000000-i} for i in range(80)]
        self.finder=TaskFinder(self.bar)

    def tearDown(self):
        self.finder.close();self.finder.deleteLater();fixtures.InteractionTests.tearDown(self)

    def test_filters_are_local_and_selection_survives_refresh(self):
        self.finder.view.setCurrentIndex(self.finder.model.index(12,0))
        self.data['catalog']=[dict(row) for row in self.data['catalog']];self.finder.refresh(self.data)
        self.assertEqual(self.finder.view.currentIndex().data(Qt.ItemDataRole.UserRole)['id'],'12')
        self.finder.search.setText('task 1')
        self.finder.projects.setCurrentIndex(self.finder.projects.findData('App'))
        self.assertTrue(all(r['project']=='App' and '1' in r['title'] for r in self.finder.model.rows))
        self.provider.refresh.assert_not_called();self.provider.request_reset.assert_not_called()

    def test_unchanged_refresh_does_not_reset_model(self):
        with patch.object(self.finder.model,'beginResetModel') as reset:
            for _ in range(30):self.finder.refresh(self.data)
            reset.assert_not_called()

    def test_narrow_window_keeps_rows_inside_viewport_without_horizontal_scroll(self):
        self.finder.resize(560,300);self.finder.grab();self.finder.view.doItemsLayout()
        self.assertLessEqual(self.finder.view.visualRect(self.finder.model.index(0,0)).width(),self.finder.view.viewport().width())
        self.assertEqual(self.finder.view.horizontalScrollBar().maximum(),0)

    def test_initial_window_fits_a_smaller_available_screen(self):
        bounds=QRect(0,0,820,600);screen=Mock();screen.availableGeometry.return_value=bounds
        with patch.object(self.bar,'screen',return_value=screen):finder=TaskFinder(self.bar)
        self.assertTrue(bounds.contains(finder.geometry()));finder.close();finder.deleteLater()

    def test_data_change_between_press_and_release_does_not_open_replacement(self):
        self.finder.remember_press(self.finder.model.index(0,0))
        self.data['catalog']=self.data['catalog'][1:];self.finder.refresh(self.data)
        with patch.object(self.bar,'open_task') as opened:
            self.finder.open_clicked(self.finder.model.index(0,0));opened.assert_not_called()

    def test_enter_opens_selected_task_and_failure_keeps_window_available(self):
        self.finder.view.setCurrentIndex(self.finder.model.index(3,0))
        with patch.object(self.bar,'open_task',return_value=True) as opened,patch.object(self.finder,'hide') as hide:
            event=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier)
            self.application.sendEvent(self.finder.view,event)
            self.assertEqual(opened.call_args.args[0]['id'],'3');hide.assert_called_once()
        with patch.object(self.bar,'open_task',return_value=False),patch.object(self.finder,'hide') as hide:
            self.finder.open_selected();hide.assert_not_called()

    def test_empty_states_and_untitled_are_translated_and_tooltips_escape_titles(self):
        self.data['catalog']=[{'id':'a','title':'','project':'','updated_at':0},{'id':'b','title':'<b>Literal</b>','project':'','updated_at':0}]
        self.bar.settings['language']='zh-CN';self.finder.refresh(self.data)
        self.assertEqual(self.finder.model.rows[0]['title'],'未命名任务')
        self.assertIn('&lt;b&gt;',self.finder.model.index(1,0).data(Qt.ItemDataRole.ToolTipRole))
        self.finder.search.setText('not found');self.assertEqual(self.finder.empty.text(),'没有匹配的任务')
        self.assertEqual(self.finder.count.text(),'结果：0')

    def test_accessible_row_includes_localized_status_and_time(self):
        self.data['tasks']=[{'id':'0','title':'Task 0','project':'Docs','running':True}]
        self.bar.settings['language']='zh-CN';self.finder.refresh(self.data)
        spoken=self.finder.model.index(0,0).data(Qt.ItemDataRole.AccessibleTextRole)
        self.assertIn('进行中',spoken);self.assertIn(self.finder.model.rows[0]['stamp'],spoken)

    def test_totals_are_numeric_sortable_in_both_directions_with_unknown_last(self):
        self.finder.statistics_button.setChecked(True)
        self.data['catalog']=self.data['catalog'][:3]
        self.data['task_statistics']={'0':{'ready':True,'tokens':9000000,'seconds':80,'turns':2},
                                      '1':{'ready':True,'tokens':120000000,'seconds':120,'turns':9,'partial':True}}
        self.finder.refresh(self.data);self.finder.choose_sort(4)
        self.assertEqual([row['id'] for row in self.finder.model.rows],['1','0','2'])
        self.finder.choose_sort(4);self.assertEqual([row['id'] for row in self.finder.model.rows],['0','1','2'])
        row=self.finder.model.rows[1];self.assertEqual(cell_text(row,4,'100M'),'1.2 ×100M');self.assertEqual(cell_text(row,3),'≥ 2m')
        self.assertEqual(self.finder.model.headerData(5,Qt.Orientation.Horizontal),'Turns')
        partial={**row,'total_tokens':160000,'tokens_partial':True}
        self.assertEqual(cell_text(partial,4,'M'),'≥ 0.1M')

    def test_statistics_updates_preserve_selected_task(self):
        self.finder.statistics_button.setChecked(True)
        self.finder.view.setCurrentIndex(self.finder.model.index(3,1))
        self.data['task_statistics']={'3':{'ready':True,'tokens':100,'seconds':40,'turns':1}}
        self.finder.refresh(self.data)
        self.assertEqual(self.finder.view.currentIndex().data(Qt.ItemDataRole.UserRole)['id'],'3')
        self.assertEqual(self.finder.model.rows[3]['total_tokens'],100)
        self.assertIn('<0.1M',self.finder.model.index(3,4).data(Qt.ItemDataRole.AccessibleTextRole))
        self.assertEqual(self.finder.scope.text(),'All local history')

    def test_indexing_shows_known_lower_bounds_and_byte_progress(self):
        self.finder.statistics_button.setChecked(True)
        self.data['catalog']=self.data['catalog'][:1]
        self.data['task_statistics']={'0':{'ready':False,'tokens':120000000,'seconds':120,'turns':9,
            'partial':True,'tokens_partial':True,'turns_partial':True,'indexed_bytes':25,'total_bytes':100}}
        self.finder.refresh(self.data);row=self.finder.model.rows[0]
        self.assertEqual(cell_text(row,3),'≥ 2m');self.assertEqual(cell_text(row,4,'100M'),'≥ 1.2 ×100M')
        self.assertEqual(cell_text(row,5),'≥ 9');self.assertIn('25%',self.finder.count.text())
        self.data['task_statistics']={'0':dict(self.data['task_statistics']['0'],ready=True,partial=False,tokens_partial=False,turns_partial=False,indexed_bytes=100)}
        self.finder.refresh(self.data)
        self.assertEqual(cell_text(self.finder.model.rows[0],5),'9');self.assertNotIn('Indexing',self.finder.count.text())

    def test_search_keeps_parent_totals_and_selection_without_temporary_side_rows(self):
        parent='00000000-0000-4000-8000-000000000001';side='00000000-0000-4000-8000-000000000002'
        self.data['catalog']=[]
        self.data['tasks']=[dict(id=parent,title='Shared title',project='App',running=True,task_role='main'),
                            dict(id=side,parent_id=parent,navigation_id=parent,title='Shared title',project='App',running=True,task_role='side',side_chat=True)]
        self.data['task_statistics']={parent:dict(ready=True,tokens=81000000,seconds=80,turns=2)}
        self.finder.refresh(self.data);self.assertEqual(self.finder.model.rowCount(),1)
        row=self.finder.model.rows[0]
        self.assertEqual(row['id'],parent);self.assertEqual(row['total_tokens'],81000000)
        self.assertFalse({'side_chat','task_role','parent_id','navigation_id'} & row.keys())
        spoken=self.finder.model.index(0,0).data(Qt.ItemDataRole.AccessibleTextRole)
        self.assertNotIn('Main',spoken);self.assertNotIn('Side',spoken)
        self.finder.view.setCurrentIndex(self.finder.model.index(0,1))
        self.finder.search.setText('Shared')
        self.data['tasks'][1].update(running=False,unread=True)
        with patch.object(self.finder.model,'replace',wraps=self.finder.model.replace) as replace:
            self.finder.refresh(self.data);replace.assert_not_called()
        self.assertEqual(self.finder.view.currentIndex().data(Qt.ItemDataRole.UserRole)['id'],parent)
        with patch('codex_taskbar.app.os.startfile') as opened:
            self.assertTrue(self.bar.open_task(row));opened.assert_called_once_with('codex://threads/'+parent)

    def test_default_search_has_four_columns_and_does_not_index_history(self):
        self.assertEqual([i for i in range(7) if not self.finder.view.isColumnHidden(i)],[0,1,2,6])
        self.assertTrue(self.finder.units.isHidden());self.assertEqual(self.finder.scope.text(),'Recorded tasks')
        self.provider.set_statistics_active.reset_mock()
        self.finder.showEvent(QShowEvent())
        self.provider.set_statistics_active.assert_called_once_with(False)
        with patch.object(self.finder.model,'replace') as replace:
            self.data['task_statistics']={'0':{'ready':False,'tokens':100,'indexed_bytes':20,'total_bytes':100}}
            self.finder.refresh(self.data);replace.assert_not_called()
        self.assertNotIn('Indexing',self.finder.count.text())

    def test_statistics_disclosure_preserves_selection_filter_and_pauses_indexing(self):
        self.finder.search.setText('Task 1');self.finder.projects.setCurrentIndex(self.finder.projects.findData('App'))
        self.finder.view.setCurrentIndex(self.finder.model.index(2,1))
        selected=self.finder.view.currentIndex().data(Qt.ItemDataRole.UserRole)['id']
        with patch.object(self.finder,'isVisible',return_value=True):
            self.finder.statistics_button.setChecked(True)
            self.provider.set_statistics_active.assert_called_with(True)
            self.assertEqual(self.finder.view.currentIndex().data(Qt.ItemDataRole.UserRole)['id'],selected)
            self.assertTrue(self.bar.settings['show_task_statistics']);self.save.assert_called()
            self.assertFalse(any(self.finder.view.isColumnHidden(i) for i in (3,4,5)))
            self.finder.choose_sort(4);self.finder.statistics_button.setChecked(False)
            self.assertEqual((self.finder.sort_column,self.finder.sort_descending),(6,True))
            self.provider.set_statistics_active.assert_called_with(False)
            self.assertEqual(self.finder.search.text(),'Task 1');self.assertEqual(self.finder.projects.currentData(),'App')
            self.assertEqual(self.finder.view.currentIndex().data(Qt.ItemDataRole.UserRole)['id'],selected)
            self.finder.statistics_button.setChecked(True);self.finder.hideEvent(QHideEvent())
            self.provider.set_statistics_active.assert_called_with(False)

    def test_statistics_choice_is_used_by_a_new_finder_and_keyboard_toggle(self):
        self.bar.settings['show_task_statistics']=True
        finder=TaskFinder(self.bar)
        try:
            self.assertTrue(finder.statistics_button.isChecked());self.assertFalse(finder.view.isColumnHidden(4))
            for kind in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):
                self.application.sendEvent(finder.statistics_button,QKeyEvent(kind,Qt.Key.Key_Space,Qt.KeyboardModifier.NoModifier))
            self.assertFalse(finder.statistics);self.assertFalse(self.bar.settings['show_task_statistics'])
        finally:finder.close();finder.deleteLater()

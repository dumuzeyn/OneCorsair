import unittest

from media_sources import detect_source, extract_media_links, normalize_media_url


class MediaLinkTests(unittest.TestCase):
    def test_mixed_share_text_and_links_without_scheme(self):
        links = extract_media_links(
            'Видео: https://youtu.be/abc. TikTok: vt.tiktok.com/ZSabc/ '
            'Instagram: (www.instagram.com/reel/abc/?igsh=test). Likee: https://likee.video/v/abc')
        self.assertEqual(links, ['https://youtu.be/abc', 'https://vt.tiktok.com/ZSabc/',
                                 'https://www.instagram.com/reel/abc/?igsh=test', 'https://likee.video/v/abc'])
        self.assertEqual([detect_source(url) for url in links], ["YouTube", "TikTok", "Instagram", "Likee"])

    def test_direct_tiktok_is_canonicalized_but_short_links_are_preserved(self):
        self.assertEqual(normalize_media_url('https://tiktok.com/@creator/video/123?x=1'),
                         'https://www.tiktok.com/@creator/video/123?x=1')
        for url in ('https://vm.tiktok.com/ZSabc/', 'https://vt.tiktok.com/ZSabc/',
                    'https://www.tiktok.com/t/ZSabc/'):
            self.assertEqual(normalize_media_url(url), url)
            self.assertEqual(detect_source(url), 'TikTok')

    def test_domain_lookalikes_do_not_receive_a_trusted_site_label(self):
        for url in ('https://notinstagram.com/reel/abc', 'https://instagram.com.example.org/reel/abc',
                    'https://tiktok.com@elsewhere.example/video/123'):
            self.assertIsNone(detect_source(url))

    def test_query_parameters_and_local_media_links_are_preserved(self):
        urls = ['https://www.instagram.com/p/abc/?igsh=abc&source=share', 'http://127.0.0.1:8181/test.mp4']
        self.assertEqual(extract_media_links('\n'.join(urls)), urls)
        self.assertEqual(extract_media_links('Смотритеhttps://vm.tiktok.com/ZSabc/'),
                         ['https://vm.tiktok.com/ZSabc/'])

    def test_cookie_help_uses_the_linked_site(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from mp3_ship_gui import MP3ShipApp

        with tempfile.TemporaryDirectory() as temporary:
            app = MP3ShipApp(settings_path=Path(temporary) / 'settings.json')
            app.withdraw()
            try:
                app.urls_text.insert('1.0', 'https://www.instagram.com/reel/abc/')
                with patch('mp3_ship_gui.messagebox.showinfo') as help_box, \
                        patch('mp3_ship_gui.webbrowser.open') as browser:
                    app._show_cookies_help()
                self.assertIn('Instagram', help_box.call_args.args[1])
                self.assertEqual(browser.call_args_list[0].args[0], 'https://www.instagram.com/')
                self.assertEqual(app.links_label.cget('text'), 'Ссылка')
                labels = [widget.cget('text') for widget, _key in app.localized_widgets]
                self.assertNotIn('Папка, качество и файл cookies запоминаются.', labels)
            finally:
                for callback in app.tk.call('after', 'info'):
                    app.after_cancel(callback)
                app.destroy()

from devbridge.i18n_util import set_lang, t


def test_strings_exist_in_both_languages():
    keys_to_check = ["welcome", "qgis_found", "done"]
    for lang in ("en", "ka"):
        set_lang(lang)
        for key in keys_to_check:
            value = t(key, path="X")
            assert value and value != key
    set_lang("en")


def test_missing_key_falls_back_to_key_name():
    set_lang("en")
    assert t("this_key_does_not_exist") == "this_key_does_not_exist"

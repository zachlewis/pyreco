__FILENAME__ = cms_plugins
from django.conf import settings
from django.forms.fields import CharField
from django.utils.translation import ugettext_lazy as _

from cms import __version__ as cms_version
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from djangocms_text_ckeditor.widgets import TextEditorWidget
from djangocms_text_ckeditor.models import Text
from djangocms_text_ckeditor.utils import plugin_tags_to_user_html
from djangocms_text_ckeditor.forms import TextForm


class TextPlugin(CMSPluginBase):
    model = Text
    name = _("Text")
    form = TextForm
    render_template = "cms/plugins/text.html"
    change_form_template = "cms/plugins/text_plugin_change_form.html"

    def get_editor_widget(self, request, plugins, pk, placeholder, language):
        """
        Returns the Django form Widget to be used for
        the text area
        """
        return TextEditorWidget(installed_plugins=plugins, pk=pk, placeholder=placeholder, plugin_language=language)

    def get_form_class(self, request, plugins, pk, placeholder, language):
        """
        Returns a subclass of Form to be used by this plugin
        """
        # We avoid mutating the Form declared above by subclassing
        class TextPluginForm(self.form):
            pass

        widget = self.get_editor_widget(request, plugins, pk, placeholder, language)
        TextPluginForm.declared_fields["body"] = CharField(
            widget=widget, required=False
        )
        return TextPluginForm

    def get_form(self, request, obj=None, **kwargs):
        plugins = plugin_pool.get_text_enabled_plugins(
            self.placeholder,
            self.page
        )
        pk = self.cms_plugin_instance.pk
        form = self.get_form_class(request, plugins, pk, self.cms_plugin_instance.placeholder,
                                   self.cms_plugin_instance.language)
        kwargs['form'] = form  # override standard form
        return super(TextPlugin, self).get_form(request, obj, **kwargs)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        """
        We override the change form template path
        to provide backwards compatibility with CMS 2.x
        """
        ckeditor_basepath = '{0}/ckeditor/'.format(settings.STATIC_URL)
        if ckeditor_basepath.startswith('//'):
            protocol = 'https' if request.is_secure else 'http'
            ckeditor_basepath = '{0}:{1}'.format(protocol, ckeditor_basepath)
        context.update({'CKEDITOR_BASEPATH': ckeditor_basepath})
        if cms_version.startswith('2'):
            context['change_form_template'] = "admin/cms/page/plugin_change_form.html"
        return super(TextPlugin, self).render_change_form(request, context, add, change, form_url, obj)

    def render(self, context, instance, placeholder):
        context.update({
            'body': plugin_tags_to_user_html(
                instance.body,
                context,
                placeholder
            ),
            'placeholder': placeholder,
            'object': instance
        })
        return context

    def save_model(self, request, obj, form, change):
        obj.clean_plugins()
        super(TextPlugin, self).save_model(request, obj, form, change)


plugin_pool.register_plugin(TextPlugin)

########NEW FILE########
__FILENAME__ = fields
from django.db import models
from django.contrib.admin import widgets as admin_widgets
from djangocms_text_ckeditor.html import clean_html
from djangocms_text_ckeditor.widgets import TextEditorWidget
try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ['^djangocms_text_ckeditor\.fields\.HTMLField'])
except ImportError:
    pass


class HTMLField(models.TextField):
    def formfield(self, **kwargs):
        defaults = {'widget': TextEditorWidget}
        defaults.update(kwargs)

        # override the admin widget
        if defaults['widget'] == admin_widgets.AdminTextareaWidget:
            defaults['widget'] = TextEditorWidget

        return super(HTMLField, self).formfield(**defaults)

    def clean(self, value, model_instance):
        value = super(HTMLField, self).clean(value, model_instance)
        return clean_html(value, full=False)
########NEW FILE########
__FILENAME__ = forms

from django import forms
from django.forms.models import ModelForm
from djangocms_text_ckeditor.models import Text


class TextForm(ModelForm):
    body = forms.CharField()

    class Meta:
        model = Text
        exclude = (
            'page',
            'position',
            'placeholder',
            'language',
            'plugin_type',
        )

########NEW FILE########
__FILENAME__ = html
# -*- coding: utf-8 -*-
try:
    from io import BytesIO as StringIO
except:
    from StringIO import StringIO
import uuid
from html5lib import sanitizer, serializer, treebuilders, treewalkers
import html5lib
import re
import base64
from PIL import Image
from .settings import (TEXT_SAVE_IMAGE_FUNCTION, TEXT_ADDITIONAL_TAGS,
                       TEXT_ADDITIONAL_ATTRIBUTES)
from djangocms_text_ckeditor.utils import plugin_to_tag


def _get_default_parser():
    sanitizer.HTMLSanitizer.acceptable_elements.extend(TEXT_ADDITIONAL_TAGS)
    sanitizer.HTMLSanitizer.acceptable_attributes.extend(TEXT_ADDITIONAL_ATTRIBUTES)
    sanitizer.HTMLSanitizer.allowed_elements = (
        sanitizer.HTMLSanitizer.acceptable_elements +
        sanitizer.HTMLSanitizer.mathml_elements +
        sanitizer.HTMLSanitizer.svg_elements)
    sanitizer.HTMLSanitizer.allowed_attributes = (
        sanitizer.HTMLSanitizer.acceptable_attributes +
        sanitizer.HTMLSanitizer.mathml_attributes +
        sanitizer.HTMLSanitizer.svg_attributes)

    return html5lib.HTMLParser(tokenizer=sanitizer.HTMLSanitizer,
                               tree=treebuilders.getTreeBuilder("dom"))
DEFAULT_PARSER = _get_default_parser()


def clean_html(data, full=True, parser=DEFAULT_PARSER):
    """
    Cleans HTML from XSS vulnerabilities using html5lib
    
    If full is False, only the contents inside <body> will be returned (without
    the <body> tags).
    """
    if full:
        dom_tree = parser.parse(data)
    else:
        dom_tree = parser.parseFragment(data)
    walker = treewalkers.getTreeWalker("dom")
    stream = walker(dom_tree)
    s = serializer.htmlserializer.HTMLSerializer(omit_optional_tags=False,
                                                 quote_attr_values=True)
    return u''.join(s.serialize(stream))

def extract_images(data, plugin):
    """
    extracts base64 encoded images from drag and drop actions in browser and saves
    those images as plugins
    """
    if not TEXT_SAVE_IMAGE_FUNCTION:
        return data
    tree_builder = html5lib.treebuilders.getTreeBuilder('dom')
    parser = html5lib.html5parser.HTMLParser(tree = tree_builder)
    dom = parser.parse(data)
    found = False
    for img in dom.getElementsByTagName('img'):
        src = img.getAttribute('src')
        if not src.startswith('data:'):
            # nothing to do
            continue
        width = img.getAttribute('width')
        height = img.getAttribute('height')
        # extract the image data
        data_re = re.compile(r'data:(?P<mime_type>[^"]*);(?P<encoding>[^"]*),(?P<data>[^"]*)')
        m = data_re.search(src)
        dr = m.groupdict()
        mime_type = dr['mime_type']
        image_data = dr['data']
        if mime_type.find(";"):
            mime_type = mime_type.split(";")[0]
        try:
            image_data = base64.b64decode(image_data)
        except:
            image_data = base64.urlsafe_b64decode(image_data)
        try:
            image_type = mime_type.split("/")[1]
        except IndexError:
            # No image type specified -- will convert to jpg below if it's valid image data
            image_type = ""
        image = StringIO(image_data)
        # genarate filename and normalize image format
        if image_type == "jpg" or image_type == "jpeg":
            file_ending = "jpg"
        elif image_type == "png":
            file_ending = 'png'
        elif image_type == "gif":
            file_ending = "gif"
        else:
            # any not "web-safe" image format we try to convert to jpg
            im = Image.open(image)
            new_image = StringIO()
            file_ending = "jpg"
            im.save(new_image, "JPEG")
            new_image.seek(0)
            image = new_image
        filename = u"%s.%s" % (uuid.uuid4(), file_ending)
        # transform image into a cms plugin
        image_plugin = img_data_to_plugin(filename, image, parent_plugin=plugin, width=width, height=height)
        # render the new html for the plugin
        new_img_html = plugin_to_tag(image_plugin)
        # replace the original image node with the newly created cms plugin html
        img.parentNode.replaceChild(parser.parseFragment(new_img_html).childNodes[0], img)
        found = True
    if found:
        return u''.join([y.toxml() for y in dom.getElementsByTagName('body')[0].childNodes])
    else:
        return data


def img_data_to_plugin(filename, image, parent_plugin, width=None, height=None):
    func_name = TEXT_SAVE_IMAGE_FUNCTION.split(".")[-1]
    module = __import__(".".join(TEXT_SAVE_IMAGE_FUNCTION.split(".")[:-1]), fromlist=[func_name])
    func = getattr(module, func_name)
    return func(filename, image, parent_plugin, width=width, height=height)


if __name__ == "__main__":
    extract_images("""<p>
    sada dadad asdas dsasd<img alt="" src="data:image/jpeg;base64,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" /></p>""", object())
    extract_images("""<p>
    sada dadad asdas dsasd<img alt="" src="data:image/jpeg;encoding:utf8;base64,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" /></p>""", object())

########NEW FILE########
__FILENAME__ = 0001_initial
# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    depends_on = (
        ('cms', '0001_initial.py'),
    )

    def forwards(self, orm):
        # Adding model 'Text'
        db.create_table('cmsplugin_text', (
            ('cmsplugin_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['cms.CMSPlugin'], unique=True, primary_key=True)),
            ('body', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('djangocms_text_ckeditor', ['Text'])


    def backwards(self, orm):
        # Deleting model 'Text'
        db.delete_table('cmsplugin_text')


    models = {
        'cms.cmsplugin': {
            'Meta': {'object_name': 'CMSPlugin'},
            'changed_date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'creation_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(2012, 12, 11, 0, 0)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '15', 'db_index': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['cms.CMSPlugin']", 'null': 'True', 'blank': 'True'}),
            'placeholder': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['cms.Placeholder']", 'null': 'True'}),
            'plugin_type': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'position': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'cms.placeholder': {
            'Meta': {'object_name': 'Placeholder'},
            'default_width': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'slot': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'})
        },
        'djangocms_text_ckeditor.text': {
            'Meta': {'object_name': 'Text', 'db_table': "'cmsplugin_text'", '_ormbases': ['cms.CMSPlugin']},
            'body': ('django.db.models.fields.TextField', [], {}),
            'cmsplugin_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['cms.CMSPlugin']", 'unique': 'True', 'primary_key': 'True'})
        }
    }

    complete_apps = ['djangocms_text_ckeditor']

########NEW FILE########
__FILENAME__ = 0002_rename_plugin
# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models, connection


class Migration(SchemaMigration):

    def forwards(self, orm):
        table_names = connection.introspection.table_names()
        if 'cmsplugin_text' in table_names:
            db.rename_table('cmsplugin_text', 'djangocms_text_ckeditor_text')

    def backwards(self, orm):
        db.rename_table('djangocms_text_ckeditor_text', 'cmsplugin_text')

    models = {
        'cms.cmsplugin': {
            'Meta': {'object_name': 'CMSPlugin'},
            'changed_date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'creation_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '15', 'db_index': 'True'}),
            'level': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'lft': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['cms.CMSPlugin']", 'null': 'True', 'blank': 'True'}),
            'placeholder': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['cms.Placeholder']", 'null': 'True'}),
            'plugin_type': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'}),
            'position': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'rght': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'}),
            'tree_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True'})
        },
        'cms.placeholder': {
            'Meta': {'object_name': 'Placeholder'},
            'default_width': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'slot': ('django.db.models.fields.CharField', [], {'max_length': '50', 'db_index': 'True'})
        },
        u'djangocms_text_ckeditor.text': {
            'Meta': {'object_name': 'Text', 'db_table': "u'cmsplugin_text'"},
            'body': ('django.db.models.fields.TextField', [], {}),
            u'cmsplugin_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['cms.CMSPlugin']", 'unique': 'True', 'primary_key': 'True'})
        }
    }

    complete_apps = ['djangocms_text_ckeditor']
########NEW FILE########
__FILENAME__ = models
import re
from django.db import models
from cms.models import CMSPlugin
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.utils.translation import ugettext_lazy as _
import sys
from djangocms_text_ckeditor.utils import plugin_tags_to_id_list, replace_plugin_tags, plugin_to_tag
from djangocms_text_ckeditor.html import clean_html, extract_images


class AbstractText(CMSPlugin):
    """Abstract Text Plugin Class"""
    body = models.TextField(_("body"))

    search_fields = ('body',)
    disable_child_plugins = True

    class Meta:
        abstract = True

    def __unicode__(self):
        return Truncator(strip_tags(self.body)).words(3, truncate="...")

    def save(self, *args, **kwargs):
        body = self.body
        body = extract_images(body, self)
        body = clean_html(body, full=False)
        self.body = body
        super(AbstractText, self).save(*args, **kwargs)

    def clean_plugins(self):
        ids = plugin_tags_to_id_list(self.body)
        plugins = CMSPlugin.objects.filter(parent=self)
        for plugin in plugins:
            if not plugin.pk in ids:
                plugin.delete() #delete plugins that are not referenced in the text anymore

    def post_copy(self, old_instance, ziplist):
        """
        Fix references to plugins
        """
        replace_ids = {}
        for new, old in ziplist:
            replace_ids[old.pk] = new.pk
        self.body = replace_plugin_tags(old_instance.get_plugin_instance()[0].body, replace_ids)
        self.save()

    def get_translatable_content(self):
        translatable_content = super(AbstractText, self).get_translatable_content()
        if not translatable_content:
            return False

        for field, value in translatable_content.items():
            # Check for an embedded LinkPlugin
            matches = re.findall(
                r'(<img alt="(Link[^"]*)" id="plugin_obj_([\d]*)" src="([^"]*)" title="(Link[^"]*)">)', value
            )

            if matches:
                for match in matches:
                    try:
                        link_plugin = CMSPlugin.objects.get(pk=match[2]).get_plugin_instance()[0]
                    except CMSPlugin.DoesNotExist:
                        sys.stderr.write("ERROR: Could not find plugin with pk %s!\n" % str(match[2]))
                        continue

                    text = '<a plugin="%s" href="%s" target="%s" alt="%s" title="%s" img_src="%s">%s</a>' % (
                        match[2], link_plugin.link(), link_plugin.target, match[1],
                        match[4], match[3], link_plugin.name
                    )
                    translatable_content[field] = value.replace(match[0], text)

        return translatable_content

    def set_translatable_content(self, fields):
        for field, value in fields.items():
            # Check for 'serialized' link plugin
            exp = r'(<a plugin="([\d]*)" href="[^"]*" target="[^"]*" alt="([^"]*)" title="([^"]*)" ' \
                  'img_src="([^"]*)">(.*[^</a>])</a>)'
            matches = re.findall(exp, value)
            if matches:
                for match in matches:
                    try:
                        linkplugin = CMSPlugin.objects.get(pk=match[1]).get_plugin_instance()[0]
                    except CMSPlugin.DoesNotExist:
                        sys.stderr.write("ERROR: Could not find plugin with pk %s\n" % str(match[0]))

                    # Save changes to linkplugin
                    linkplugin.name = match[5]
                    linkplugin.save()

                    # Save changes to parent text plugin
                    text = '<img alt="%s" id="plugin_obj_%s" src="%s" title="%s">' % (match[2], match[1], match[4], match[3])
                    value = value.replace(match[0], text)

            setattr(self, field, value)
        self.save()

        return True

    def notify_on_autoadd_children(self, request, conf, children):
        """
        Method called when we auto add children to this plugin via 
        default_plugins/<plugin>/children in CMS_PLACEHOLDER_CONF.
        we must replace some strings with child tag for the CKEDITOR.
        Strings are "%(_tag_child_<order>)s" with the inserted order of chidren
        """
        replacements = dict()
        order = 1
        for child in children:
            replacements['_tag_child_'+str(order)] = plugin_to_tag(child)
            order+=1
        self.body = self.body % replacements
        self.save()


class Text(AbstractText):

    class Meta:
        abstract = False

########NEW FILE########
__FILENAME__ = picture_save
from cms.models.pluginmodel import CMSPlugin
from django.conf import settings
import os


def create_picture_plugin(filename, file, parent_plugin, **kwargs):
    try:
        from djangocms_picture.models import Picture
    except ImportError:
        from cms.plugins.picture.models import Picture

    pic = Picture()
    pic.placeholder = parent_plugin.placeholder
    pic.parent = parent_plugin
    pic.position = CMSPlugin.objects.filter(parent=parent_plugin).count()
    pic.language = parent_plugin.language
    pic.plugin_type = 'PicturePlugin'
    path = pic.get_media_path(filename)
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.exists(os.path.dirname(full_path)):
        os.makedirs(os.path.dirname(full_path))
    pic.image = path
    f = open(full_path, "wb")
    f.write(file.read())
    f.close()
    pic.save()
    return pic

########NEW FILE########
__FILENAME__ = settings
from django.conf import settings

#See http://docs.cksource.com/ckeditor_api/symbols/CKEDITOR.config.html for all settings

CKEDITOR_SETTINGS = getattr(settings, 'CKEDITOR_SETTINGS', {
    'language': '{{ language }}',
    'toolbar': 'CMS',
    'skin': 'moono',
#    'stylesSet': [
#        {'name': 'Custom Style', 'element': 'h3', 'styles': {'color': 'Blue'}}
#    ],
    'toolbarCanCollapse': False,
})

INSTALLED_APPS = getattr(settings, 'INSTALLED_APPS', [])
if 'cms.plugins.picture' in INSTALLED_APPS or 'djangocms_picture' in INSTALLED_APPS:
    save_function_default = 'djangocms_text_ckeditor.picture_save.create_picture_plugin'
else:
    save_function_default = None

TEXT_SAVE_IMAGE_FUNCTION = getattr(settings, 'TEXT_SAVE_IMAGE_FUNCTION', save_function_default)
TEXT_ADDITIONAL_TAGS = getattr(settings, 'TEXT_ADDITIONAL_TAGS', ())
TEXT_ADDITIONAL_ATTRIBUTES = getattr(settings, 'TEXT_ADDITIONAL_ATTRIBUTES', ())
########NEW FILE########
__FILENAME__ = utils
import re
from django.template.defaultfilters import force_escape
import django

from cms.models import CMSPlugin
from distutils.version import LooseVersion
from django.utils.functional import LazyObject
from django.core.files.storage import get_storage_class
import os

OBJ_ADMIN_RE_PATTERN = r'<img [^>]*\bid="plugin_obj_(\d+)"[^>]*/?>'
OBJ_ADMIN_RE = re.compile(OBJ_ADMIN_RE_PATTERN)

def plugin_to_tag(obj):
    return u'<img src="%(icon_src)s" alt="%(icon_alt)s" title="%(icon_alt)s" id="plugin_obj_%(id)d" />' % \
               dict(id=obj.id,
                    icon_src=force_escape(obj.get_instance_icon_src()),
                    icon_alt=force_escape(obj.get_instance_icon_alt()),
                    )

def plugin_tags_to_id_list(text, regex=OBJ_ADMIN_RE):
    ids = regex.findall(text)
    return [int(id) for id in ids if id.isdigit()]

def plugin_tags_to_user_html(text, context, placeholder):
    """
    Convert plugin object 'tags' into the form for public site.

    context is the template context to use, placeholder is the placeholder name
    """
    plugin_map = _plugin_dict(text)
    def _render_tag(m):
        plugin_id = int(m.groups()[0])
        try:
            obj = plugin_map[plugin_id]
            obj._render_meta.text_enabled = True
        except KeyError:
            # Object must have been deleted.  It cannot be rendered to
            # end user so just remove it from the HTML altogether
            return u''
        return obj.render_plugin(context, placeholder)
    return OBJ_ADMIN_RE.sub(_render_tag, text)

def replace_plugin_tags(text, id_dict):
    def _replace_tag(m):
        plugin_id = int(m.groups()[0])
        new_id = id_dict.get(plugin_id)
        try:
            obj = CMSPlugin.objects.get(pk=new_id)
        except CMSPlugin.DoesNotExist:
            # Object must have been deleted.  It cannot be rendered to
            # end user, or edited, so just remove it from the HTML
            # altogether
            return u''
        return u'<img src="%(icon_src)s" alt="%(icon_alt)s" title="%(icon_alt)s" id="plugin_obj_%(id)d" />' % \
               dict(id=new_id,
                    icon_src=force_escape(obj.get_instance_icon_src()),
                    icon_alt=force_escape(obj.get_instance_icon_alt()),
                    )
    return OBJ_ADMIN_RE.sub(_replace_tag, text)


def _plugin_dict(text, regex=OBJ_ADMIN_RE):
    try:
        from cms.utils.plugins import downcast_plugins
    except ImportError:
        from cms.plugins.utils import downcast_plugins

    plugin_ids = plugin_tags_to_id_list(text, regex)
    plugin_list = downcast_plugins(CMSPlugin.objects.filter(pk__in=plugin_ids), select_placeholder=True)
    return dict((plugin.pk, plugin) for plugin in plugin_list)


"""
The following class is taken from https://github.com/jezdez/django/compare/feature/staticfiles-templatetag
and should be removed and replaced by the django-core version in 1.4
"""
default_storage = 'django.contrib.staticfiles.storage.StaticFilesStorage'
if LooseVersion(django.get_version()) < LooseVersion('1.3'):
    default_storage = 'staticfiles.storage.StaticFilesStorage'


class ConfiguredStorage(LazyObject):
    def _setup(self):
        from django.conf import settings
        self._wrapped = get_storage_class(getattr(settings, 'STATICFILES_STORAGE', default_storage))()

configured_storage = ConfiguredStorage()

def static_url(path):
    '''
    Helper that prefixes a URL with STATIC_URL and cms
    '''
    if not path:
        return ''
    return configured_storage.url(os.path.join('', path))

########NEW FILE########
__FILENAME__ = widgets
import json

from django.conf import settings
from django.forms import Textarea
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation.trans_real import get_language

import djangocms_text_ckeditor.settings as text_settings


class TextEditorWidget(Textarea):
    def __init__(self, attrs=None, installed_plugins=None, pk=None, placeholder=None, plugin_language=None):
        """
        Create a widget for editing text + plugins.

        installed_plugins is a list of plugins to display that are text_enabled
        """
        if attrs is None:
            attrs = {}

        self.ckeditor_class = 'CMS_CKEditor'
        if self.ckeditor_class not in attrs.get('class', '').join(' '):
            new_class = attrs.get('class', '') + ' %s' % self.ckeditor_class
            attrs.update({
                'class': new_class.strip()
            })

        super(TextEditorWidget, self).__init__(attrs)
        self.installed_plugins = installed_plugins
        self.pk = pk
        self.placeholder = placeholder
        self.plugin_language = plugin_language

    def render_textarea(self, name, value, attrs=None):
        return super(TextEditorWidget, self).render(name, value, attrs)

    def render_additions(self, name, value, attrs=None):
        language = get_language().split('-')[0]
        context = {
            'ckeditor_class': self.ckeditor_class,
            'name': name,
            'language': language,
            'settings': language.join(json.dumps(text_settings.CKEDITOR_SETTINGS).split("{{ language }}")),
            'STATIC_URL': settings.STATIC_URL,
            'installed_plugins': self.installed_plugins,
            'plugin_pk': self.pk,
            'plugin_language': self.plugin_language,
            'placeholder': self.placeholder
        }
        return mark_safe(render_to_string('cms/plugins/widgets/ckeditor.html', context))

    def render(self, name, value, attrs=None):
        return self.render_textarea(name, value, attrs) + \
               self.render_additions(name, value, attrs)

########NEW FILE########
__FILENAME__ = schemamigration
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'mptt',
    'cms',
    'menus',
    'djangocms_text_ckeditor',
    'south',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

TEMPLATE_CONTEXT_PROCESSORS = [
    'django.core.context_processors.auth',
    'django.core.context_processors.i18n',
    'django.core.context_processors.request',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'cms.context_processors.media',
    'sekizai.context_processors.sekizai',
]

ROOT_URLCONF = 'cms.urls'


def schemamigration():
    # turn ``schemamigration.py --initial`` into
    # ``manage.py schemamigration cmsplugin_disqus --initial`` and setup the
    # enviroment
    from django.conf import settings

    from django.core.management import ManagementUtility
    settings.configure(
        INSTALLED_APPS=INSTALLED_APPS,
        ROOT_URLCONF=ROOT_URLCONF,
        DATABASES=DATABASES,
        TEMPLATE_CONTEXT_PROCESSORS=TEMPLATE_CONTEXT_PROCESSORS
    )
    argv = list(sys.argv)
    argv.insert(1, 'schemamigration')
    argv.insert(2, 'djangocms_text_ckeditor')
    utility = ManagementUtility(argv)
    utility.execute()

if __name__ == "__main__":
    schemamigration()

########NEW FILE########

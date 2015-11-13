__FILENAME__ = run_dilla
from django.core.management.base import BaseCommand
from optparse import make_option
from dilla import Dilla
import sys


class Command(BaseCommand):
    help = Dilla.__doc__

    option_list = BaseCommand.option_list + (
    make_option('--cycles',
        action='store',
        dest='cycles',
        default=1,
        help='Number of spam cycles to perform. Default: 1'),
    make_option('--apps',
        action='store',
        dest='apps',
        default=None,
        help='Comma-separated app list to spam. Default: settings.DILLA_APPS'),
    make_option('--no-input',
        action='store_true',
        dest='no_input',
        default=False,
        help='Do not ask user for spam confirmation'),
    make_option('--no-coin',
        action='store_true',
        dest='use_coin',
        default=False,
        help='Do not use coin toss'),
    )

    def handle(self, *args, **options):
        if options['apps'] is not None:
            apps = options['apps'].split(",")
        else:
            apps = None

        if not options['no_input']:
            self.stdout.write('Dilla is going to spam your database. \
                    Do you wish to proceed? (Y/N)')
            confirm = sys.stdin.readline().replace('\n', '').upper()
            if not confirm == 'Y':
                self.stdout.write('Aborting.\n')
                sys.exit(1)

        d = Dilla(apps=apps, \
                cycles=int(options['cycles']), \
                use_coin=not options['use_coin'])

        apps, affected, filled, omitted = d.run()

        self.stdout.write("Dilla finished!\n\
        %d app(s) spammed %d row(s) affected, \
        %d field(s) filled, %d field(s) ommited.\nThank you!)" % \
                (apps, affected, filled, omitted)
                )

########NEW FILE########
__FILENAME__ = spammers
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random
import os
import decimal
import logging
import datetime

from django.conf import settings
from django.contrib.webdesign import lorem_ipsum
from django.core.files.base import ContentFile
from django.db.models import URLField, get_model
from django.template.defaultfilters import slugify

from dilla import spam

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

log = logging.getLogger('dilla')

dictionary = getattr(settings, 'DICTIONARY', "/usr/share/dict/words")
if os.path.exists(dictionary) and \
        not getattr(settings, 'DILLA_USE_LOREM_IPSUM', False):
    d = open(dictionary, "r").readlines()
    _random_words = \
            lambda n: " ".join([random.choice(d).lower().rstrip() \
            for i in range(n)])
    _random_paragraph = lambda: _random_words(30).capitalize()
    _random_paragraphs = lambda n: \
            ".\n\n".join([_random_paragraph() for i in range(n)])
else:
    _random_words = lorem_ipsum.words
    _random_paragraphs = lambda n: ".\n\n".join(lorem_ipsum.paragraphs(n))


@spam.global_handler('CharField')
def random_words(record, field):
    # this is somewhat nasty, URLField.get_internal_type()
    # returns 'CharField'
    if isinstance(field, URLField):
        return "http://%s.com/%s/?%s=%s" % tuple(_random_words(4).split(" "))

    max_length = field.max_length
    words = _random_words(3).decode('utf8').encode('utf8')
    if max_length < len(words):
        return words[:max_length]
    return words


@spam.global_handler('TextField')
def random_text(record, field):
    text_content = _random_paragraphs(4)
    if field.max_length:
        text_content = text_content[:field.max_length]
    return text_content


@spam.global_handler('IPAddressField')
def random_ip(record, field):
    return ".".join([str(random.randrange(0, 255)) for i in range(0, 4)])


@spam.global_handler('SlugField')
def random_slug(record, field):
    slug = random_words(record, field).replace(" ", "-")
    return ''.join(ch for ch in slug if ch.isalnum() or ch == '-')


@spam.global_handler('NullBooleanField')
@spam.global_handler('BooleanField')
def random_bool(record, field):
    return bool(random.randint(0, 1))


@spam.global_handler('EmailField')
def random_email(record, field):
    return "%s@%s.%s" % ( \
             slugify(_random_words(1)),
             slugify(_random_words(1)),
             random.choice(["com", "org", "net", "gov", "eu"])
             )


@spam.global_handler('SmallIntegerField')
@spam.global_handler('IntegerField')
def random_int(record, field):
    return random.randint(-10000, 10000)


@spam.global_handler('BigIntegerField')
def random_bigint(record, field):
    return random.randint(- 10 ** 10, 10 ** 10)


@spam.global_handler('DecimalField')
def random_decimal(record, field):
    return decimal.Decimal(str(random.random() + random.randint(1, 20)))


@spam.global_handler('PositiveIntegerField')
def random_posint(record, field):
    return random.randint(0, 10000)


@spam.global_handler('DateField')
@spam.global_handler('TimeField')
@spam.global_handler('DateTimeField')
def random_datetime(record, field):
    """
    Calculate random datetime object between last and next month.
    Django interface is pretty tollerant at this point, so three
    decorators instead of three handlers here.
    """

    # 1 month ~= 30d ~= 720h ~= 43200min
    random_minutes = random.randint(-43200, 43200)
    return datetime.datetime.now() + datetime.timedelta(minutes=random_minutes)


@spam.global_handler('FileField')  # ImageField's internal type is FileField
def random_file(record, field):
    """
    For your convinience, all files and images generated by Dilla
    will have ``dilla_`` prefix.

    For ImageFields this handler will generate images using PIL.
    Since it is required by Django to have PIL installed when
    using ImageFields, there is no point in providing
    alternate routine other than lazy import.
    """
    #destination = os.path.join(field.storage.location, field.upload_to)
    #if not os.path.exists(destination):
    #    os.makedirs(destination)

    def _random_image(field):
        log.debug("Generating identicon image")
        from identicon import identicon
        name = "dilla_%s.png" % random_slug(record, field)
        icon = identicon.render_identicon( \
                random.randint(5 ** 5, 10 ** 10), \
                random.randint(64, 250))
        # using storage
        tmp_file = StringIO()
        icon.save(tmp_file, 'PNG')
        name = field.generate_filename(record.obj, name)
        saved_name = field.storage.save(name, ContentFile(tmp_file.getvalue()))
        return saved_name

    def _random_textfile(field):
        log.debug("Generating text file")
        name = "dilla_%s.txt" % random_slug(record, field)
        name = field.generate_filename(record.obj, name)
        saved_name = field.storage.save(name, ContentFile(_random_words(10)))
        return saved_name

    try:
        from django.db.models import ImageField
        if isinstance(field, ImageField):
            return _random_image(field)
        return _random_textfile(field)
    except ImportError, e:
        log.warn(e)
        return _random_textfile(field)


@spam.global_handler('ForeignKey')
def random_fk(record, field, limit=None):
    Related = field.rel.to
    log.debug('Trying to find related object: %s' % Related)
    models_to_exclude = getattr(settings, 'DILLA_EXCLUDE_MODELS', None)
    if models_to_exclude:
        try:
            excluded_models = [get_model(*m.split('.')) \
                    for m in models_to_exclude]
            if Related in excluded_models:
                log.info('skipping related object [%s] for %s' % \
                        (Related, field.name))
                return None
        except ValueError:
            pass
    try:
        query = Related.objects.all().order_by('?')
        if field.rel.limit_choices_to:
            log.debug('Field %s has limited choices. \
                    Applying to query.' % field)
            query.filter(**field.rel.limit_choices_to)
        if limit:
            return query[:limit]
        return query[0]
    except IndexError, e:
        log.warn('Could not find any related objects for %s' % field.name)
        return None
    except Exception, e:
        log.critical(str(e))
        raise


@spam.global_handler('ManyToManyField')
def random_manytomany(record, field):
    return random_fk(record, field, random.randint(1, 5))

########NEW FILE########

from django.db import migrations
import re


def sync_subject_year_levels(apps, schema_editor):
    Subject = apps.get_model('api', 'Subject')
    CourseClass = apps.get_model('api', 'CourseClass')

    for s in Subject.objects.all():
        classes = CourseClass.objects.filter(subject=s).select_related('group')
        years = []
        for c in classes:
            m = re.search(r'2[3-6]', c.group.group_name)
            if m:
                code = m.group(0)
                y = {'26': 1, '25': 2, '24': 3, '23': 4}.get(code, 1)
                years.append(y)
        if years:
            s.year_level = min(years)
            s.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sync_subject_year_levels, reverse_code=migrations.RunPython.noop),
    ]

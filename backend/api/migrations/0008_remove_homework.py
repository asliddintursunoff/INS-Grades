from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_alter_paymentauditlog_extracted_amount'),
    ]

    operations = [
        migrations.DeleteModel(
            name='HomeworkSubmission',
        ),
        migrations.DeleteModel(
            name='Homework',
        ),
    ]

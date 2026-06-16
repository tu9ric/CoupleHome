from django.db import migrations


def assign_existing_items_to_spaces(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    CoupleSpace = apps.get_model('Todo', 'CoupleSpace')
    Task = apps.get_model('Todo', 'Task')
    SharedFile = apps.get_model('Todo', 'SharedFile')
    CoupleEvent = apps.get_model('Todo', 'CoupleEvent')
    ChatMessage = apps.get_model('Todo', 'ChatMessage')

    spaces_by_user_id = {}

    for user in User.objects.all():
        space = CoupleSpace.objects.create(name=f"{user.username}'s home", owner=user)
        space.members.add(user)
        spaces_by_user_id[user.id] = space

    for task in Task.objects.filter(space__isnull=True):
        if task.user_id in spaces_by_user_id:
            task.space = spaces_by_user_id[task.user_id]
            task.save(update_fields=['space'])

    for shared_file in SharedFile.objects.filter(space__isnull=True):
        if shared_file.owner_id in spaces_by_user_id:
            shared_file.space = spaces_by_user_id[shared_file.owner_id]
            shared_file.save(update_fields=['space'])

    for event in CoupleEvent.objects.filter(space__isnull=True):
        if event.owner_id in spaces_by_user_id:
            event.space = spaces_by_user_id[event.owner_id]
            event.save(update_fields=['space'])

    for message in ChatMessage.objects.filter(space__isnull=True):
        if message.user_id in spaces_by_user_id:
            message.space = spaces_by_user_id[message.user_id]
            message.save(update_fields=['space'])


class Migration(migrations.Migration):

    dependencies = [
        ('Todo', '0003_couplespace_chatmessage_space_coupleevent_space_and_more'),
    ]

    operations = [
        migrations.RunPython(assign_existing_items_to_spaces, migrations.RunPython.noop),
    ]

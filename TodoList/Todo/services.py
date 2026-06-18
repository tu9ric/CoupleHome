from django.db.models import Count, Q
from django.utils import timezone

from .models import ChatMessage, CoupleEvent, CoupleSpace, SharedFile, Task


QUESTION_PROMPTS = (
    'What made us smile today?',
    'What should we cook together this week?',
    'Which shared plan needs a tiny next step?',
    'What is one thing we can make easier for each other?',
    'Which memory should we save in OurHome?',
)


def get_user_spaces(user):
    return CoupleSpace.objects.filter(members=user)


def get_active_space(request):
    spaces = get_user_spaces(request.user)
    active_space = spaces.filter(id=request.session.get('active_space_id')).first()

    if active_space is None:
        active_space = spaces.first() or create_personal_space(request.user)
        request.session['active_space_id'] = active_space.id

    return active_space


def create_personal_space(user):
    space = CoupleSpace.objects.create(
        name=f"{user.username}'s home",
        owner=user,
    )
    space.members.add(user)
    return space


def add_space_context(request, context, active_nav):
    active_space = get_active_space(request)
    context.update({
        'active_nav': active_nav,
        'active_space': active_space,
        'spaces': get_user_spaces(request.user),
    })
    return active_space


def get_question_prompt(date=None):
    current_date = date or timezone.localdate()
    return QUESTION_PROMPTS[current_date.toordinal() % len(QUESTION_PROMPTS)]


def get_space_overview(space, chat_limit=4):
    tasks = Task.objects.filter(space=space)
    files = SharedFile.objects.filter(space=space)
    upcoming_events = CoupleEvent.objects.filter(
        space=space,
        event_date__gte=timezone.localdate(),
    )

    task_counts = tasks.aggregate(
        count=Count('id', filter=Q(complete=False)),
        completed_count=Count('id', filter=Q(complete=True)),
        total_count=Count('id'),
    )

    return {
        **task_counts,
        'file_count': files.count(),
        'favorite_files': files.filter(favorite=True)[:4],
        'recent_files': files[:4],
        'event_count': upcoming_events.count(),
        'events': upcoming_events[:4],
        'chat_messages': ChatMessage.objects.filter(space=space)[:chat_limit],
        'question_prompt': get_question_prompt(),
    }

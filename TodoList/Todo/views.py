from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import (
    AccountDeleteForm,
    AccountPasswordChangeForm,
    AccountProfileForm,
    AccountRecoveryForm,
    AddSpaceMemberForm,
    CaseInsensitiveAuthenticationForm,
    CaseInsensitiveUserCreationForm,
    ChatMessageEditForm,
    ChatMessageForm,
    CoupleEventForm,
    CoupleSpaceForm,
    SharedFileForm,
    SharedFileUpdateForm,
    TaskForm,
)
from .mixins import AssignSpaceMixin, OwnedChatMessageMixin, SpaceQuerysetMixin
from .models import ChatMessage, CoupleEvent, SharedFile, Task
from .security import decrypt_bytes
from .services import (
    add_space_context,
    get_active_space,
    get_space_overview,
    get_user_spaces,
)


User = get_user_model()


class TaskList(LoginRequiredMixin, ListView):
    model = Task
    context_object_name = 'task'
    template_name = 'todo/task_list.html'

    def get_queryset(self):
        queryset = Task.objects.filter(space=get_active_space(self.request))
        search_input = self.request.GET.get('search-area', '').strip()
        status_filter = self.request.GET.get('status', '').strip()
        category_filter = self.request.GET.get('category', '').strip()

        if search_input:
            queryset = queryset.filter(title__icontains=search_input)

        if status_filter == 'active':
            queryset = queryset.filter(complete=False)
        elif status_filter == 'completed':
            queryset = queryset.filter(complete=True)

        if category_filter:
            queryset = queryset.filter(category=category_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_space = add_space_context(self.request, context, 'todo')
        user_tasks = Task.objects.filter(space=active_space)
        status_filter = self.request.GET.get('status', '').strip()

        if status_filter not in ['active', 'completed']:
            status_filter = ''

        context['search_input'] = self.request.GET.get('search-area', '').strip()
        context['status_filter'] = status_filter
        context['category_filter'] = self.request.GET.get('category', '').strip()
        context['categories'] = user_tasks.exclude(
            category__isnull=True
        ).exclude(
            category=''
        ).values_list('category', flat=True).distinct().order_by('category')
        context.update(get_space_overview(active_space, chat_limit=5))
        context['visible_count'] = context['task'].count()
        context['chat_form'] = ChatMessageForm()
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'todo/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_space = add_space_context(self.request, context, 'dashboard')
        context.update(get_space_overview(active_space))
        return context


class SharedFileList(LoginRequiredMixin, ListView):
    model = SharedFile
    context_object_name = 'files'
    template_name = 'todo/shared_file_list.html'

    def get_queryset(self):
        queryset = SharedFile.objects.filter(space=get_active_space(self.request))
        category = self.request.GET.get('category', '').strip()
        favorite = self.request.GET.get('favorite', '').strip()

        if category:
            queryset = queryset.filter(category=category)
        if favorite == '1':
            queryset = queryset.filter(favorite=True)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_space = add_space_context(self.request, context, 'files')
        context['category_filter'] = self.request.GET.get('category', '').strip()
        context['favorite_filter'] = self.request.GET.get('favorite', '').strip()
        context['file_count'] = SharedFile.objects.filter(space=active_space).count()
        context['favorite_count'] = SharedFile.objects.filter(space=active_space, favorite=True).count()
        context['file_categories'] = SharedFile.CATEGORY_CHOICES
        return context


class CoupleEventList(LoginRequiredMixin, ListView):
    model = CoupleEvent
    context_object_name = 'events'
    template_name = 'todo/event_list.html'

    def get_queryset(self):
        return CoupleEvent.objects.filter(space=get_active_space(self.request))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_space = add_space_context(self.request, context, 'events')
        context['upcoming_count'] = CoupleEvent.objects.filter(
            space=active_space,
            event_date__gte=timezone.localdate(),
        ).count()
        return context


class ChatPage(LoginRequiredMixin, TemplateView):
    template_name = 'todo/chat.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_space = add_space_context(self.request, context, 'chat')
        latest_messages = ChatMessage.objects.filter(
            space=active_space,
        ).select_related('user', 'reply_to', 'reply_to__user').order_by('-id')[:50]
        context['chat_messages'] = list(reversed(latest_messages))
        context['latest_chat_message_id'] = (
            context['chat_messages'][-1].id
            if context['chat_messages']
            else 0
        )
        context['chat_form'] = ChatMessageForm()
        return context


class SettingsPage(LoginRequiredMixin, TemplateView):
    template_name = 'todo/settings.html'
    allowed_themes = {'light', 'dark'}
    allowed_languages = {'en', 'ru'}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_space = add_space_context(self.request, context, 'settings')
        context['theme'] = self.request.session.get('theme', 'light')
        context['language'] = self.request.session.get('language', 'en')
        context['space_form'] = CoupleSpaceForm()
        context['member_form'] = AddSpaceMemberForm()
        context['profile_form'] = AccountProfileForm(instance=self.request.user)
        context['password_form'] = AccountPasswordChangeForm(self.request.user)
        context['delete_account_form'] = AccountDeleteForm(self.request.user)
        context['members'] = active_space.members.order_by('username')
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('settings_action', 'preferences')
        handler = getattr(self, f'handle_{action}', self.handle_preferences)
        return handler(request, get_active_space(request))

    def handle_create_space(self, request, active_space):
        form = CoupleSpaceForm(request.POST)
        if form.is_valid():
            space = form.save(commit=False)
            space.owner = request.user
            space.save()
            space.members.add(request.user)
            request.session['active_space_id'] = space.id
        return redirect('settings')

    def handle_switch_space(self, request, active_space):
        space = get_user_spaces(request.user).filter(
            id=request.POST.get('space_id'),
        ).first()
        if space:
            request.session['active_space_id'] = space.id
        return redirect('settings')

    def handle_add_member(self, request, active_space):
        form = AddSpaceMemberForm(request.POST)
        if form.is_valid():
            user = User.objects.get(
                username__iexact=form.cleaned_data['username'],
            )
            active_space.members.add(user)
        return redirect('settings')

    def handle_remove_member(self, request, active_space):
        if active_space.owner_id == request.user.id:
            member = active_space.members.filter(
                id=request.POST.get('member_id'),
            ).exclude(id=active_space.owner_id).first()
            if member:
                active_space.members.remove(member)
        return redirect('settings')

    def handle_profile(self, request, active_space):
        form = AccountProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
        return redirect('settings')

    def handle_password(self, request, active_space):
        form = AccountPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
        return redirect('settings')

    def handle_deactivate_account(self, request, active_space):
        form = AccountDeleteForm(request.user, request.POST)
        if form.is_valid():
            request.user.is_active = False
            request.user.save(update_fields=['is_active'])
            logout(request)
            return redirect('login')
        return redirect('settings')

    def handle_preferences(self, request, active_space):
        theme = request.POST.get('theme', 'light')
        language = request.POST.get('language', 'en')
        request.session['theme'] = theme if theme in self.allowed_themes else 'light'
        request.session['language'] = language if language in self.allowed_languages else 'en'
        return redirect('settings')


class TaskDetail(LoginRequiredMixin, SpaceQuerysetMixin, DetailView):
    model = Task
    context_object_name = 'task'
    template_name = 'todo/task.html'

class TaskCreate(LoginRequiredMixin, AssignSpaceMixin, CreateView):
    model = Task
    form_class = TaskForm
    success_url = reverse_lazy('task')

    user_field = 'user'


class TaskUpdate(LoginRequiredMixin, SpaceQuerysetMixin, UpdateView):
    model = Task
    form_class = TaskForm
    success_url = reverse_lazy('task')

class TaskDelete(LoginRequiredMixin, SpaceQuerysetMixin, DeleteView):
    model = Task
    context_object_name = 'task'
    success_url = reverse_lazy('task')

class CustomLoginView(LoginView):
    template_name = 'todo/login.html'
    authentication_form = CaseInsensitiveAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('dashboard')


class RegisterPage(FormView):
    template_name = 'todo/register.html'
    form_class = CaseInsensitiveUserCreationForm
    redirect_authenticated_user = True
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        user = form.save()
        if user is not None:
            login(self.request, user)
        return super(RegisterPage, self).form_valid(form)

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return redirect('dashboard')
        return super(RegisterPage, self).get(*args, **kwargs)


class AccountRecoveryPage(FormView):
    template_name = 'todo/account_recovery.html'
    form_class = AccountRecoveryForm
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class SharedFileCreate(LoginRequiredMixin, AssignSpaceMixin, CreateView):
    model = SharedFile
    form_class = SharedFileForm
    template_name = 'todo/shared_file_form.html'
    success_url = reverse_lazy('files')

    user_field = 'owner'


class SharedFileDelete(LoginRequiredMixin, SpaceQuerysetMixin, DeleteView):
    model = SharedFile
    context_object_name = 'file'
    template_name = 'todo/shared_file_confirm_delete.html'
    success_url = reverse_lazy('files')

class SharedFileUpdate(LoginRequiredMixin, SpaceQuerysetMixin, UpdateView):
    model = SharedFile
    form_class = SharedFileUpdateForm
    template_name = 'todo/shared_file_edit_form.html'
    success_url = reverse_lazy('files')

class CoupleEventCreate(LoginRequiredMixin, AssignSpaceMixin, CreateView):
    model = CoupleEvent
    form_class = CoupleEventForm
    template_name = 'todo/event_form.html'
    success_url = reverse_lazy('events')

    user_field = 'owner'


class ChatMessageCreate(LoginRequiredMixin, AssignSpaceMixin, CreateView):
    model = ChatMessage
    form_class = ChatMessageForm
    success_url = reverse_lazy('chat')

    user_field = 'user'

    def form_valid(self, form):
        active_space = get_active_space(self.request)
        reply_to_id = form.cleaned_data.get('reply_to')
        if reply_to_id:
            form.instance.reply_to = ChatMessage.objects.filter(
                id=reply_to_id,
                space=active_space,
            ).first()

        response = super().form_valid(form)
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'id': self.object.id,
                'html': render_chat_message(self.request, self.object),
            }, status=201)
        return response


class ChatMessageUpdate(LoginRequiredMixin, OwnedChatMessageMixin, UpdateView):
    model = ChatMessage
    form_class = ChatMessageEditForm
    template_name = 'todo/chat_message_form.html'
    success_url = reverse_lazy('chat')

class ChatMessageDelete(LoginRequiredMixin, OwnedChatMessageMixin, DeleteView):
    model = ChatMessage
    context_object_name = 'message'
    template_name = 'todo/chat_message_confirm_delete.html'
    success_url = reverse_lazy('chat')

@login_required
def download_chat_attachment(request, pk):
    message = get_object_or_404(ChatMessage, pk=pk, space=get_active_space(request))
    if not message.data:
        return HttpResponse(status=404)

    response = HttpResponse(decrypt_bytes(message.data), content_type=message.content_type or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{message.file_name}"'
    return response


@login_required
def chat_notifications(request):
    after_id = request.GET.get('after', '0')
    try:
        after_id = int(after_id)
    except ValueError:
        after_id = 0

    active_space = get_active_space(request)
    messages = ChatMessage.objects.filter(
        space=active_space,
        id__gt=after_id,
    ).exclude(user=request.user).order_by('id')[:10]

    payload = []
    for message in messages:
        text = message.display_message
        if not text and message.attachment_type != ChatMessage.TEXT:
            text = dict(ChatMessage.ATTACHMENT_CHOICES).get(message.attachment_type, 'Attachment')

        payload.append({
            'id': message.id,
            'author': message.user.username,
            'message': text,
            'attachment_type': message.attachment_type,
        })

    latest_message = ChatMessage.objects.filter(space=active_space).order_by('-id').first()
    return JsonResponse({
        'latest_id': latest_message.id if latest_message else after_id,
        'messages': payload,
    })


@login_required
def chat_updates(request):
    try:
        after_id = max(int(request.GET.get('after', 0)), 0)
    except (TypeError, ValueError):
        after_id = 0

    messages = list(
        ChatMessage.objects.filter(
            space=get_active_space(request),
            id__gt=after_id,
        ).select_related('user', 'reply_to', 'reply_to__user').order_by('id')[:50]
    )
    return JsonResponse({
        'latest_id': messages[-1].id if messages else after_id,
        'messages': [
            {
                'id': message.id,
                'html': render_chat_message(request, message),
                'is_own': message.user_id == request.user.id,
                'author': message.user.username,
                'message': message.display_message or message.get_attachment_type_display(),
                'created_at': message.created.isoformat(),
            }
            for message in messages
        ],
    })


def render_chat_message(request, message):
    return render_to_string(
        'todo/_chat_message.html',
        {'message': message},
        request=request,
    )


@login_required
def download_shared_file(request, pk):
    shared_file = get_object_or_404(SharedFile, pk=pk, space=get_active_space(request))
    response = HttpResponse(bytes(shared_file.data), content_type=shared_file.content_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{shared_file.file_name}"'
    return response

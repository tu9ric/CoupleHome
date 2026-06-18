from .services import add_space_context, get_active_space


class SpaceContextMixin:
    active_nav = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        add_space_context(self.request, context, self.active_nav)
        return context


class SpaceQuerysetMixin:
    space_field = 'space'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{
            self.space_field: get_active_space(self.request),
        })


class AssignSpaceMixin:
    user_field = None
    space_field = 'space'

    def form_valid(self, form):
        setattr(form.instance, self.space_field, get_active_space(self.request))
        if self.user_field:
            setattr(form.instance, self.user_field, self.request.user)
        return super().form_valid(form)


class OwnedChatMessageMixin(SpaceQuerysetMixin):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

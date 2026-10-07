from django.contrib import admin

from .models import Finding, ProductionRecord, Project, ProjectMetrics, ProjectUpdate


class ReadOnlyAdmin(admin.ModelAdmin):
    """Admin hanya untuk menelusuri data; sumber kebenaran tetap file + ingest."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Project)
class ProjectAdmin(ReadOnlyAdmin):
    list_display = ["project_id", "project_name", "pic", "deadline", "reported_status", "reported_progress_pct"]


@admin.register(ProjectUpdate)
class ProjectUpdateAdmin(ReadOnlyAdmin):
    list_display = ["update_id", "project_id", "timestamp", "source_type", "source_name"]
    list_filter = ["project_id", "source_type"]
    search_fields = ["message"]


@admin.register(ProductionRecord)
class ProductionRecordAdmin(ReadOnlyAdmin):
    list_display = ["source_record_id", "project_id", "timestamp", "source_system", "record_type"]
    list_filter = ["project_id", "record_type"]


@admin.register(ProjectMetrics)
class ProjectMetricsAdmin(ReadOnlyAdmin):
    list_display = ["project", "attention", "observed_pct", "pace_ratio", "days_remaining"]


@admin.register(Finding)
class FindingAdmin(ReadOnlyAdmin):
    list_display = ["project", "severity", "rule", "explanation"]
    list_filter = ["project", "severity", "rule"]

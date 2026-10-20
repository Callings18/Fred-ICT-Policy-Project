def register(app):
    from app.views.account import bp as account_bp
    from app.views.activities import bp as activities_bp
    from app.views.alerts import bp as alerts_bp
    from app.views.api import bp as api_bp
    from app.views.auditlog import bp as audit_bp
    from app.views.auth import bp as auth_bp
    from app.views.dashboard import bp as dashboard_bp
    from app.views.devices import bp as devices_bp
    from app.views.employees import bp as employees_bp
    from app.views.findings import bp as findings_bp
    from app.views.hr import bp as hr_bp
    from app.views.policies import bp as policies_bp
    from app.views.reports import bp as reports_bp
    from app.views.reviews import bp as reviews_bp
    from app.views.roles import bp as roles_bp
    from app.views.settings import bp as settings_bp
    from app.views.notifications import bp as notifications_bp
    from app.views.users import bp as users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(findings_bp)
    app.register_blueprint(policies_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(api_bp)

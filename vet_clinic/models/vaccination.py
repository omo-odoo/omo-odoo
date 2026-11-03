from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

REMINDER_DAYS = 30


class VetVaccination(models.Model):
    _name = 'vet.vaccination'
    _description = 'Vaccination'
    _order = 'date desc'

    animal_id = fields.Many2one('vet.animal', string='Animal', required=True, ondelete='cascade')
    owner_id = fields.Many2one(related='animal_id.owner_id', store=True, string='Propriétaire')
    vaccine_id = fields.Many2one('vet.vaccine', string='Vaccin', required=True)
    date = fields.Date('Date', required=True, default=fields.Date.context_today)
    next_date = fields.Date('Prochain rappel', compute='_compute_next_date', store=True, readonly=False)
    batch_number = fields.Char('N° de lot')
    veterinarian_id = fields.Many2one('res.users', string='Vétérinaire', default=lambda self: self.env.user)
    consultation_id = fields.Many2one('vet.consultation', string='Consultation', ondelete='set null')
    is_last = fields.Boolean(compute='_compute_is_last', string='Dernière injection')
    state = fields.Selection([
        ('valid', 'Valide'), ('due_soon', 'Rappel proche'), ('expired', 'Expiré'),
    ], compute='_compute_state', string='État')

    @api.depends('date', 'vaccine_id.validity_months')
    def _compute_next_date(self):
        for rec in self:
            if rec.date and rec.vaccine_id:
                rec.next_date = rec.date + relativedelta(months=rec.vaccine_id.validity_months)
            else:
                rec.next_date = False

    @api.depends('next_date')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.next_date:
                rec.state = 'valid'
            elif rec.next_date < today:
                rec.state = 'expired'
            elif rec.next_date <= today + timedelta(days=REMINDER_DAYS):
                rec.state = 'due_soon'
            else:
                rec.state = 'valid'

    @api.depends('animal_id.vaccination_ids.date', 'vaccine_id')
    def _compute_is_last(self):
        for rec in self:
            same = rec.animal_id.vaccination_ids.filtered(lambda v: v.vaccine_id == rec.vaccine_id)
            rec.is_last = bool(same) and rec == max(same, key=lambda v: (v.date or fields.Date.today(), v.id))

    @api.model
    def _cron_vaccine_reminders(self):
        """Crée une activité « À faire » sur l'animal pour chaque rappel arrivant à échéance."""
        today = fields.Date.context_today(self)
        limit = today + timedelta(days=REMINDER_DAYS)
        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        model_id = self.env['ir.model']._get_id('vet.animal')
        upcoming = self.search([('next_date', '<=', limit), ('animal_id.state', '=', 'alive')])
        for vacc in upcoming.filtered('is_last'):
            summary = f"Rappel vaccin {vacc.vaccine_id.name}"
            already = self.env['mail.activity'].search_count([
                ('res_model_id', '=', model_id),
                ('res_id', '=', vacc.animal_id.id),
                ('summary', '=', summary),
            ])
            if already:
                continue
            vacc.animal_id.activity_schedule(
                activity_type_id=todo_type.id if todo_type else False,
                summary=summary,
                note=f"Contacter {vacc.owner_id.name} : rappel prévu le {vacc.next_date}.",
                date_deadline=max(vacc.next_date, today),
                user_id=(vacc.veterinarian_id or self.env.user).id,
            )

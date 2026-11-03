from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class VetAnimal(models.Model):
    _name = 'vet.animal'
    _description = 'Animal'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'name'

    name = fields.Char('Nom', required=True, tracking=True)
    reference = fields.Char('Référence', readonly=True, copy=False, default='Nouveau')
    owner_id = fields.Many2one('res.partner', string='Propriétaire', required=True, tracking=True)
    species_id = fields.Many2one('vet.species', string='Espèce', required=True, tracking=True)
    breed_id = fields.Many2one('vet.breed', string='Race',
                               domain="[('species_id', '=', species_id)]")
    sex = fields.Selection([('male', 'Mâle'), ('female', 'Femelle'), ('unknown', 'Inconnu')],
                           string='Sexe', default='unknown')
    neutered = fields.Boolean('Stérilisé(e)')
    birth_date = fields.Date('Date de naissance')
    age = fields.Char('Âge', compute='_compute_age')
    color = fields.Char('Robe / couleur')
    microchip = fields.Char('N° de puce', copy=False)
    weight = fields.Float('Poids actuel (kg)', digits=(6, 2), tracking=True)
    allergies = fields.Text('Allergies')
    notes = fields.Html('Notes médicales')
    state = fields.Selection([('alive', 'Vivant'), ('deceased', 'Décédé')],
                             default='alive', string='Statut', tracking=True)
    death_date = fields.Date('Date de décès')
    active = fields.Boolean(default=True)

    consultation_ids = fields.One2many('vet.consultation', 'animal_id', string='Consultations')
    vaccination_ids = fields.One2many('vet.vaccination', 'animal_id', string='Vaccinations')
    consultation_count = fields.Integer(compute='_compute_counts')
    vaccination_count = fields.Integer(compute='_compute_counts')
    last_consultation_date = fields.Datetime(compute='_compute_counts', string='Dernière consultation')
    vaccine_status = fields.Selection([
        ('ok', 'À jour'), ('soon', 'Rappel proche'), ('late', 'En retard'), ('none', 'Aucun vaccin'),
    ], compute='_compute_vaccine_status', string='Statut vaccinal')

    @api.depends('birth_date')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.birth_date:
                rec.age = False
                continue
            delta = relativedelta(today, rec.birth_date)
            if delta.years:
                rec.age = f"{delta.years} an(s) {delta.months} mois"
            else:
                rec.age = f"{delta.months} mois"

    @api.depends('consultation_ids', 'vaccination_ids')
    def _compute_counts(self):
        for rec in self:
            rec.consultation_count = len(rec.consultation_ids)
            rec.vaccination_count = len(rec.vaccination_ids)
            dates = rec.consultation_ids.mapped('date')
            rec.last_consultation_date = max(dates) if dates else False

    @api.depends('vaccination_ids.state')
    def _compute_vaccine_status(self):
        for rec in self:
            states = set(rec.vaccination_ids.filtered('is_last').mapped('state'))
            if not states:
                rec.vaccine_status = 'none'
            elif 'expired' in states:
                rec.vaccine_status = 'late'
            elif 'due_soon' in states:
                rec.vaccine_status = 'soon'
            else:
                rec.vaccine_status = 'ok'

    @api.onchange('species_id')
    def _onchange_species_id(self):
        if self.breed_id and self.breed_id.species_id != self.species_id:
            self.breed_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('vet.animal') or 'Nouveau'
        return super().create(vals_list)

    def action_mark_deceased(self):
        self.write({'state': 'deceased', 'death_date': fields.Date.context_today(self)})

    def action_view_consultations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Consultations',
            'res_model': 'vet.consultation',
            'view_mode': 'list,form,calendar',
            'domain': [('animal_id', '=', self.id)],
            'context': {'default_animal_id': self.id},
        }

    def action_view_vaccinations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vaccinations',
            'res_model': 'vet.vaccination',
            'view_mode': 'list,form',
            'domain': [('animal_id', '=', self.id)],
            'context': {'default_animal_id': self.id},
        }

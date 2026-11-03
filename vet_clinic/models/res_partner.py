from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    animal_ids = fields.One2many('vet.animal', 'owner_id', string='Animaux')
    animal_count = fields.Integer(compute='_compute_animal_count')

    def _compute_animal_count(self):
        for rec in self:
            rec.animal_count = len(rec.animal_ids)

    def action_view_animals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Animaux',
            'res_model': 'vet.animal',
            'view_mode': 'kanban,list,form',
            'domain': [('owner_id', '=', self.id)],
            'context': {'default_owner_id': self.id},
        }

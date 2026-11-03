from odoo import fields, models


class VetSpecies(models.Model):
    _name = 'vet.species'
    _description = 'Espèce animale'
    _order = 'name'

    name = fields.Char('Espèce', required=True, translate=True)
    breed_ids = fields.One2many('vet.breed', 'species_id', string='Races')
    animal_count = fields.Integer(compute='_compute_animal_count')
    active = fields.Boolean(default=True)

    def _compute_animal_count(self):
        data = self.env['vet.animal']._read_group(
            [('species_id', 'in', self.ids)], ['species_id'], ['__count'])
        counts = {species.id: count for species, count in data}
        for rec in self:
            rec.animal_count = counts.get(rec.id, 0)


class VetBreed(models.Model):
    _name = 'vet.breed'
    _description = 'Race'
    _order = 'species_id, name'

    name = fields.Char('Race', required=True)
    species_id = fields.Many2one('vet.species', string='Espèce', required=True, ondelete='cascade')


class VetVaccine(models.Model):
    _name = 'vet.vaccine'
    _description = 'Vaccin'
    _order = 'name'

    name = fields.Char('Vaccin', required=True)
    species_ids = fields.Many2many('vet.species', string='Espèces concernées')
    validity_months = fields.Integer('Validité (mois)', default=12, required=True)
    product_id = fields.Many2one('product.product', string='Article facturé')
    active = fields.Boolean(default=True)

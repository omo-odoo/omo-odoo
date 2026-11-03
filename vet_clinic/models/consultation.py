from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class VetConsultation(models.Model):
    _name = 'vet.consultation'
    _description = 'Consultation vétérinaire'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char('Numéro', readonly=True, copy=False, default='Nouveau')
    animal_id = fields.Many2one('vet.animal', string='Animal', required=True, tracking=True)
    owner_id = fields.Many2one(related='animal_id.owner_id', store=True, string='Propriétaire')
    species_id = fields.Many2one(related='animal_id.species_id', store=True, string='Espèce')
    date = fields.Datetime('Date', required=True, default=fields.Datetime.now, tracking=True)
    duration = fields.Float('Durée (h)', default=0.5)
    veterinarian_id = fields.Many2one('res.users', string='Vétérinaire',
                                      default=lambda self: self.env.user, tracking=True)
    consultation_type = fields.Selection([
        ('routine', 'Visite de routine'), ('vaccination', 'Vaccination'),
        ('emergency', 'Urgence'), ('surgery', 'Chirurgie'), ('followup', 'Suivi'),
    ], string='Type', default='routine', required=True)
    reason = fields.Char('Motif')
    weight = fields.Float('Poids mesuré (kg)', digits=(6, 2))
    temperature = fields.Float('Température (°C)', digits=(4, 1))
    symptoms = fields.Text('Symptômes / anamnèse')
    diagnosis = fields.Text('Diagnostic')
    treatment = fields.Text('Traitement / prescription')
    state = fields.Selection([
        ('draft', 'Planifiée'), ('in_progress', 'En cours'), ('done', 'Terminée'),
        ('invoiced', 'Facturée'), ('cancel', 'Annulée'),
    ], default='draft', string='Statut', tracking=True, required=True)

    line_ids = fields.One2many('vet.consultation.line', 'consultation_id', string='Actes et produits')
    vaccination_ids = fields.One2many('vet.vaccination', 'consultation_id', string='Vaccins administrés')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    amount_total = fields.Monetary('Total HT', compute='_compute_amount_total', store=True)
    invoice_id = fields.Many2one('account.move', string='Facture', readonly=True, copy=False)
    color = fields.Integer(compute='_compute_color')

    @api.depends('line_ids.subtotal')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('subtotal'))

    @api.depends('consultation_type')
    def _compute_color(self):
        colors = {'emergency': 1, 'surgery': 9, 'vaccination': 10, 'followup': 4, 'routine': 0}
        for rec in self:
            rec.color = colors.get(rec.consultation_type, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nouveau') == 'Nouveau':
                vals['name'] = self.env['ir.sequence'].next_by_code('vet.consultation') or 'Nouveau'
        return super().create(vals_list)

    # ---- Workflow -------------------------------------------------------
    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        for rec in self:
            if rec.weight:
                rec.animal_id.weight = rec.weight
        self.write({'state': 'done'})

    def action_cancel(self):
        if self.filtered(lambda c: c.state == 'invoiced'):
            raise UserError("Impossible d'annuler une consultation déjà facturée.")
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_create_invoice(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError("Ajoutez au moins un acte ou un produit avant de facturer.")
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.owner_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [Command.create({
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
            }) for line in self.line_ids],
        })
        self.write({'invoice_id': invoice.id, 'state': 'invoiced'})
        return self.action_view_invoice()

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }


class VetConsultationLine(models.Model):
    _name = 'vet.consultation.line'
    _description = 'Ligne de consultation'

    consultation_id = fields.Many2one('vet.consultation', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Article')
    name = fields.Char('Description', required=True)
    quantity = fields.Float('Quantité', default=1.0)
    price_unit = fields.Float('Prix unitaire')
    currency_id = fields.Many2one(related='consultation_id.currency_id')
    subtotal = fields.Monetary('Sous-total', compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.price_unit = self.product_id.lst_price

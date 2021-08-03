##############################################################################
#
#    Copyright (C) 2014 Leandro Ezequiel Baldi
#    <baldileandro@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from random import choice

from odoo import api, fields, models, _
from odoo.exceptions import AccessDenied, ValidationError


PARAM_PASS = "it_passkey"
PARAM_SALT = "it_passsalt"


class ItAccess(models.Model):
    _name = "it.access"
    _description = "Access"

    @api.onchange("equipment_id")
    def onchange_equipment(self):
        if self.equipment_id:
            self.partner_id = self.equipment_id.partner_id
        else:
            self.partner_id = None

    def get_random_password(self):
        for access in self:
            longitud = 16
            valores = (
                "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ<=>@#%&+"
            )
            p = ""
            p = p.join([choice(valores) for i in range(longitud)])
            access.write({"password": p, "encrypted": False})

    def get_urlsafe_key(self):

        ConfigParam = self.env["ir.config_parameter"]
        salt = None
        passphrase = ConfigParam.sudo().get_param(PARAM_PASS)
        if not passphrase:
            passphrase = base64.urlsafe_b64encode(os.urandom(64)).decode()
            salt = os.urandom(16)
            ConfigParam.sudo().set_param(PARAM_PASS, passphrase)
            ConfigParam.sudo().set_param(PARAM_SALT, base64.urlsafe_b64encode(salt).decode())
        else:
            salt = base64.urlsafe_b64decode(ConfigParam.sudo().get_param(PARAM_SALT).encode())

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256,
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

    @api.onchange("password")
    def onchange_password(self):
        self.encrypted = False

    def encrypt_password(self):

        key = self.get_urlsafe_key()
        f = Fernet(key)

        for rec in self:
            if not rec.encrypted:
                token = f.encrypt(rec.password.encode())
                rec.password = base64.urlsafe_b64encode(token)
                rec.encrypted = True
            else:
                raise ValidationError(_("Password already encrypted"))

        return True

    def decrypt_password(self):

        key = self.get_urlsafe_key()
        f = Fernet(key)

        for rec in self:
            token = base64.urlsafe_b64decode(rec.password)
            password = f.decrypt(token).decode()
            raise AccessDenied(password)

    @api.model
    def _get_partner_id(self):
        if self.env.context.get("active_model") == "it.equipment":
            equip = self.env["it.equipment"].browse(self.env.context.get("active_id"))
            if equip.partner_id:
                return equip.partner_id.id
        return False

    @api.model
    def _get_site_id(self):
        if self.env.context.get("active_model") == "it.equipment":
            equip = self.env["it.equipment"].browse(self.env.context.get("active_id"))
            if equip.site_id:
                return equip.site_id.id
        return False

    company_id = fields.Many2one(
        "res.company",
        "Company",
        required=True,
        default=lambda self: self.env["res.company"]._company_default_get(
            "account.invoice"
        ),
    )
    equipment_id = fields.Many2one("it.equipment", "Equipment", ondelete="restrict")
    site_id = fields.Many2one("it.site", "Site", ondelete="restrict", default=_get_site_id)
    name = fields.Char("Username", required=True)
    password = fields.Char()
    encrypted = fields.Boolean(default=False)
    partner_id = fields.Many2one(
        "res.partner", "Partner", domain="[('manage_it','=',1)]", default="_get_partner_id",
    )
    active = fields.Boolean(default=True)
    ssl_csr = fields.Binary("CSR")
    ssl_csr_filename = fields.Char("CSR Filename")
    ssl_cert = fields.Binary("Cert")
    ssl_cert_filename = fields.Char("Cert Filename")
    ssl_publickey = fields.Binary("Public Key")
    ssl_publickey_filename = fields.Char("Public Key Filename")
    ssl_privatekey = fields.Binary("Private Key")
    ssl_privatekey_filename = fields.Char("Private Key Filename")

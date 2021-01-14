import dataclasses

from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QDialog

from qu.ui import _ui_folder_path


class QuUNetSettingsDialog(QDialog):
    """Dialog to edit the settings of the UNetLearner.

    A copy of the passed settings is edited and returned if
    the Accept button is pressed; otherwise, None. The original
    settings are unaffected.
    """

    def __init__(self, settings, *args, **kwargs):
        """Constructor."""

        # Call base constructor
        super().__init__(*args, **kwargs)

        # Store a reference to __a copy__ of the settings
        self._settings = dataclasses.replace(settings)

        # Set up UI
        uic.loadUi(_ui_folder_path / "qu_unet_settings_dialog.ui", self)

        # Make sure to set validators where necessary
        self._set_validators()

        # Fill the fields
        self._fill_ui_fields()

        # Set the connections
        self._set_connections()

    def _set_validators(self):
        """Set validators on edit fields."""
        self.leNumEpochs.setValidator(QIntValidator(1, 1000000000, self))
        self.leValidationStep.setValidator(QIntValidator(1, 1000000000, self))
        self.leTrainingBatchSize.setValidator(QIntValidator(1, 1000000000, self))

    def _fill_ui_fields(self):
        """Fill the UI elements with the values in the settings."""
        self.leNumEpochs.setText(str(self._settings.num_epochs))
        self.leValidationStep.setText(str(self._settings.validation_step))
        self.leTrainingBatchSize.setText(str(self._settings.batch_sizes[0]))

    def _set_connections(self):
        """Plug signals and slots"""
        self.leNumEpochs.textChanged.connect(self._on_num_epochs_text_changed)
        self.leValidationStep.textChanged.connect(self._on_validation_step_text_changed)
        self.leTrainingBatchSize.textChanged.connect(self._on_training_batch_size_text_changed)

    @staticmethod
    def get_settings(settings, parent=None):
        """Static method to create the dialog and return the updated settings or None if cancelled."""
        dialog = QuUNetSettingsDialog(settings, parent)
        if QDialog.Accepted == dialog.exec_():
            return dialog._settings
        return None

    @pyqtSlot('QString', name="_on_num_epochs_text_changed")
    def _on_num_epochs_text_changed(self, str_value):
        """Number of epochs."""
        # The IntValidator allows empty strings.
        if str_value == '':
            return
        value = int(str_value)
        if value < 1:
            value = 1
            self.leNumEpochs.setText(str(value))
        self._settings.num_epochs = value

    @pyqtSlot('QString', name="_on_validation_step_text_changed")
    def _on_validation_step_text_changed(self, str_value):
        """Validation step."""
        # The IntValidator allows empty strings.
        if str_value == '':
            return
        value = int(str_value)
        if value < 1:
            value = 1
            self.leValidationStep.setText(str(value))
        self._settings.validation_step = value

    @pyqtSlot('QString', name="_on_training_batch_size_text_changed")
    def _on_training_batch_size_text_changed(self, str_value):
        """Validation step."""
        # The IntValidator allows empty strings.
        if str_value == '':
            return
        value = int(str_value)
        if value < 1:
            value = 1
            self.leTrainingBatchSize.setText(str(value))
        new_batch_sizes = (
            value,
            self._settings.batch_sizes[1],
            self._settings.batch_sizes[2],
            self._settings.batch_sizes[3]
        )
        self._settings.batch_sizes = new_batch_sizes
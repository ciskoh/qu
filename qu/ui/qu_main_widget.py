import torch
from PyQt5 import QtWidgets, uic, QtGui
from PyQt5.QtCore import pyqtSlot, QThreadPool
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QFileDialog, QAction, QMessageBox
import sys

from qu import __version__
from qu.data.model import MaskType
from qu.ui import _ui_folder_path
from qu.console import EmittingErrorStream, EmittingOutputStream
from qu.data import DataModel
from qu.ml import UNetOneHotLearner, UNetLabelsLearner
from qu.ui.threads import LearnerManager


class QuWidget(QtWidgets.QWidget):

    def __init__(self, viewer, *args, **kwargs):
        """Constructor."""

        # Call base constructor
        super().__init__(*args, **kwargs)

        # Store a reference to the napari viewer
        self._viewer = viewer

        # Set up UI
        uic.loadUi(_ui_folder_path / "qu_main_widget.ui", self)

        # Set up the menu
        self._add_qu_menu()

        # Set the connections
        self._set_connections()

        # Setup standard out and err redirection
        sys.stdout = EmittingOutputStream()
        sys.stdout.stream_signal.connect(self._on_print_output_to_console)
        sys.stderr = EmittingErrorStream()
        sys.stderr.stream_signal.connect(self._on_print_error_to_console)

        # Initialize data model
        self._data_model = DataModel()

        # Test redirection to output
        print(f"Welcome to Qu {__version__}.")

    def _add_qu_menu(self):
        """Add the Qu menu to the main window."""

        # First add a separator from the standard napari menu
        qu_menu = self._viewer.window.main_menu.addMenu(" | ")
        qu_menu.setEnabled(False)

        # Now add the Qu menu
        about_action = QAction(QIcon(":/icons/info.png"), "About", self)
        about_action.triggered.connect(self._on_qu_about_action)
        qu_menu = self._viewer.window.main_menu.addMenu("Qu")
        qu_menu.addAction(about_action)

    def _set_connections(self):
        """Connect signals and slots."""

        self.pBSelectDataRootFolder.clicked.connect(self._on_select_data_root_folder)
        self.hsImageSelector.valueChanged.connect(self._on_selector_value_changed)
        self.hsTrainingValidationSplit.valueChanged.connect(self._on_train_val_split_selector_value_changed)
        self.hsValidationTestingSplit.valueChanged.connect(self._on_val_test_split_selector_value_changed)
        self.pbTrain.clicked.connect(self._on_run_training)
        self.pbFreeMemory.clicked.connect(self._on_free_memory_and_report)
        self.pbSelectPredictionData.clicked.connect(self._on_select_data_for_prediction)

    def _update_data_selector(self) -> None:
        """Update data selector (slider)."""

        # Update the slider
        if self._data_model.num_images == 0:
            self.hsImageSelector.setMinimum(0)
            self.hsImageSelector.setMaximum(0)
            self.hsImageSelector.setValue(0)
            self.hsImageSelector.setEnabled(False)
        else:
            self.hsImageSelector.setMinimum(0)
            self.hsImageSelector.setMaximum(self._data_model.num_images - 1)
            self.hsImageSelector.setValue(self._data_model.index)
            self.hsImageSelector.setEnabled(True)

    def display(self) -> None:
        """Display current image and mask."""

        # Get current data (if there is any)
        image, mask = self._data_model.get_data_for_current_index()
        if image is None:
            self._update_data_selector()
            return

        # Display image and mask
        if 'Image' in self._viewer.layers:
            self._viewer.layers["Image"].data = image
        else:
            self._viewer.add_image(image, name="Image")

        if 'Mask' in self._viewer.layers:
            self._viewer.layers["Mask"].data = mask
        else:
            self._viewer.add_labels(mask, name="Mask")

    def _update_training_ui_elements(
            self,
            training_fraction,
            validation_fraction,
            num_train,
            num_val,
            num_test
    ):
        """Updates the ui elements associated with the training parameters."""

        training_total = int(100 * training_fraction)
        validation_total = int(100 * validation_fraction)
        training_total_str = f"Training ({training_total}% of {self._data_model.num_images})"
        validation_total_str = f"Validation:Test ({validation_total}%)"
        num_training_images = f"{num_train} training images."
        num_val_test_images = f"{num_val}:{num_test} val:test images."

        # Update the training elements
        self.lbTrainingValidationSplit.setText(training_total_str)
        self.hsTrainingValidationSplit.blockSignals(True)
        self.hsTrainingValidationSplit.setValue(training_total)
        self.hsTrainingValidationSplit.blockSignals(False)
        self.hsTrainingValidationSplit.setEnabled(True)
        self.lbNumberTrainingImages.setText(num_training_images)

        # Update the validation/test elements
        self.lbValidationTestingSplit.setText(validation_total_str)
        self.hsValidationTestingSplit.blockSignals(True)
        self.hsValidationTestingSplit.setValue(validation_total)
        self.hsValidationTestingSplit.blockSignals(False)
        self.hsValidationTestingSplit.setEnabled(True)
        self.lbNumberValidationTestingImages.setText(num_val_test_images)

    @pyqtSlot(bool, name="_on_select_data_root_folder")
    def _on_select_data_root_folder(self) -> None:
        """Ask the user to pick a data folder."""

        # Check whether we already have data loaded
        if self._data_model.num_images > 0:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("Are you sure you want to discard current data?")
            msg.setInformativeText("All data and changes will be lost.")
            msg.setWindowTitle("Qu:: Question")
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            if msg.exec_() == QMessageBox.Cancel:
                return

            # Reset current model
            self._data_model.reset()

        # Ask the user to pick a folder
        output_dir = QFileDialog.getExistingDirectory(
            None,
            "Select Data Root Directory..."
        )
        if output_dir == '':
            # The user cancelled the selection
            return

        # Set the path in the DataModel
        self._data_model.root_data_path = output_dir

        # Retrieve the (parsed) root data path
        root_data_path = self._data_model.root_data_path

        # Update the button
        self.pBSelectDataRootFolder.setText(str(root_data_path))

        # Scan the data folder
        self._data_model.scan()

        # Update the data selector
        self._update_data_selector()

        # Update the training/validation/test split sliders
        num_train, num_val, num_test = self._data_model.preview_training_split()
        self._update_training_ui_elements(
            self._data_model.training_fraction,
            self._data_model.validation_fraction,
            num_train,
            num_val,
            num_test
        )

        # Display current data
        self.display()

    @pyqtSlot(name='_on_select_data_for_prediction')
    def _on_select_data_for_prediction(self):
        """Select data for prediction."""

        print("Implement me!")

    @pyqtSlot(str, name='_on_print_output_to_console')
    def _on_print_output_to_console(self, text: str) -> None:
        """Redirect standard output to console."""

        # Append the text
        self.teLogConsole.moveCursor(QtGui.QTextCursor.End)
        self.teLogConsole.insertPlainText(text)

    @pyqtSlot(str, name='_on_print_error_to_console')
    def _on_print_error_to_console(self, text: str) -> None:
        """Redirect standard error to console."""

        # Get current color
        current_color = self.teLogConsole.textColor()

        # Set the color to red
        self.teLogConsole.setTextColor(QtGui.QColor(255, 0, 0))

        # Append the text
        self.teLogConsole.moveCursor(QtGui.QTextCursor.End)
        self.teLogConsole.insertPlainText(text)

        # Restore the color
        self.teLogConsole.setTextColor(current_color)

    @pyqtSlot(int, name="_on_selector_value_changed")
    def _on_selector_value_changed(self, value):
        """Triggered when the value of the image selector slider changes.

        Please notice that the slider has tracking off, meaning the
        value_changed signal is not emitted while the slider is being
        moved, but only at the end of the movement!
        """

        # Update the index in the data model
        self._data_model.index = value

        # Update the display
        self.display()

    @pyqtSlot(int, name="_on_train_val_split_selector_value_changed")
    def _on_train_val_split_selector_value_changed(self, value):
        """Recalculate splits and update UI elements."""

        # Update the training fraction in the data model
        self._data_model.training_fraction = float(value) / 100.0

        # Recalculate splits
        num_train, num_val, num_test = self._data_model.preview_training_split()

        # Update UI elements
        self._update_training_ui_elements(
            self._data_model.training_fraction,
            self._data_model.validation_fraction,
            num_train,
            num_val,
            num_test
        )

    @pyqtSlot(int, name="_on_val_test_split_selector_value_changed")
    def _on_val_test_split_selector_value_changed(self, value):
        """Recalculate splits and update UI elements."""

        # Update the validation fraction in the data model
        self._data_model.validation_fraction = float(value) / 100.0

        # Recalculate splits
        num_train, num_val, num_test = self._data_model.preview_training_split()

        # Update UI elements
        self._update_training_ui_elements(
            self._data_model.training_fraction,
            self._data_model.validation_fraction,
            num_train,
            num_val,
            num_test
        )

    @pyqtSlot(name="_on_run_training")
    def _on_run_training(self):
        """Instantiate the Learner (if needed) and run the training."""

        # @TODO: Retrieve the learner from the pull-down selector!

        # Instantiate the learner depending on the mask type
        if self._data_model.mask_type == MaskType.NUMPY_ONE_HOT:

            # @TODO: Store it and check if it already exists
            learner = UNetOneHotLearner(
                in_channels=1,
                out_channels=self._data_model.num_classes,
                roi_size=(384, 384),
                num_epochs=4,
                batch_sizes=(8, 1, 1),
                num_workers=(1, 1, 1),
                working_dir=self._data_model.root_data_path
            )

        else:

            # @TODO: Store it and check if it already exists
            learner = UNetLabelsLearner(
                in_channels=1,
                out_channels=self._data_model.num_classes,
                roi_size=(384, 384),
                num_epochs=4,
                batch_sizes=(8, 1, 1),
                num_workers=(1, 1, 1),
                working_dir=self._data_model.root_data_path
            )

        # Get the data
        try:
            train_image_names, train_mask_names, \
                val_image_names, val_mask_names, \
                test_image_names, test_mask_names = self._data_model.training_split()
        except ValueError as e:
            print(f"Error: {str(e)}. Aborting...", file=sys.stderr)
            return
        except Exception as x:
            print(f"{str(x)}", file=sys.stderr)
            return

        # Pass the training data to the learner
        learner.set_training_data(
            train_image_names,
            train_mask_names,
            val_image_names,
            val_mask_names,
            test_image_names,
            test_mask_names
        )

        # Instantiate the manager
        learnerManager = LearnerManager(learner)

        # Run the training in a separate Qt thread
        learnerManager.signals.started.connect(self._on_training_start)
        learnerManager.signals.errored.connect(self._on_training_error)
        learnerManager.signals.finished.connect(self._on_training_completed)
        learnerManager.signals.returned.connect(self._on_training_returned)
        QThreadPool.globalInstance().start(learnerManager)

    @pyqtSlot(name="_on_qu_about_action")
    def _on_qu_about_action(self):
        """Qu about action."""
        print("Qu version 0.0.1")

    @pyqtSlot(name="_on_training_start")
    def _on_training_start(self):
        """Called when training is started."""
        print("Training started.")

    @pyqtSlot(name="_on_training_completed")
    def _on_training_completed(self):
        """Called when training is complete."""
        print("Training completed.")

    @pyqtSlot(object, name="_on_training_returned")
    def _on_training_returned(self, value):
        """Called when training returned."""
        if bool(value):
            print(f"Training was successful.")
        else:
            print(f"Training was not successful.")

    @pyqtSlot(object, name="_on_training_error")
    def _on_training_error(self, err):
        """Called if training failed."""
        print(f"Training error: {str(err)}")

    @pyqtSlot(name="_on_free_memory_and_report")
    def _on_free_memory_and_report(self):
        """Try freeing memory on GPU and report."""
        gb = 1024 * 1024 * 1024
        if torch.cuda.is_available():
            t = round(torch.cuda.get_device_properties(0).total_memory / gb, 2)
            c = round(torch.cuda.memory_reserved(0) / gb, 2)
            a = round(torch.cuda.memory_allocated(0) / gb, 2)
            print(f"[BEFORE] Memory allocated = {a} GB, reserved = {c}, total = {t}")
            torch.cuda.empty_cache()
            c = round(torch.cuda.memory_reserved(0) / gb, 2)
            a = round(torch.cuda.memory_allocated(0) / gb, 2)
            print(f"[AFTER ] Memory allocated = {a} GB, reserved = {c}, total = {t}")
        else:
            print("GPU not available.")

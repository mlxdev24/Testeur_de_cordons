import json
import os
import threading
import time
from datetime import datetime

import flet as ft
import serial
from serial.tools import list_ports


class CableTesterFletApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Cable Tester - UART -> JSON"
        self.page.window_width = 900
        self.page.window_height = 750
        self.page.window_min_width = 850
        self.page.window_min_height = 700
        self.page.padding = 20
        self.page.theme_mode = ft.ThemeMode.SYSTEM

        # Variables d'état
        self.cmd_var = "TEST\\n"

        # Références JSON chargées
        self.references = {}
        self.active_reference = None

        # État d'identification du testeur
        self.tester_identified = False

        # Connexion série unique
        self.serial_port = None

        # Dossier Références
        self.references_dir = os.path.join(os.getcwd(), "Références")

        # Initialisation de l'interface
        self._build_ui()
        self._create_references_directory()
        self.refresh_ports()

        # Gestion de la fermeture
        self.page.on_disconnect = self.on_closing

    def _create_references_directory(self):
        """Crée le dossier Références s'il n'existe pas"""
        try:
            if not os.path.exists(self.references_dir):
                os.makedirs(self.references_dir)
                self.log_line(f"✓ Dossier 'Références' créé : {self.references_dir}")
            else:
                self.log_line(f"✓ Dossier 'Références' disponible : {self.references_dir}")
        except Exception as e:
            self.log_line(f"✗ Erreur lors de la création du dossier Références : {e}")

    def _build_ui(self):
        """Construction de l'interface utilisateur"""

        # Création des widgets réutilisables
        self.port_dropdown = ft.Dropdown(
            width=250,
            options=[],
        )

        self.identify_btn = ft.ElevatedButton(
            "🔌 Connecter",
            on_click=lambda _: self.identify_tester(),
            width=120
        )

        self.disconnect_btn = ft.ElevatedButton(
            "❌ Déconnecter",
            on_click=lambda _: self.disconnect_tester(),
            width=120,
            disabled=True
        )

        self.baud_field = ft.TextField(
            value="38400",
            width=120,
        )

        self.timeout_field = ft.TextField(
            value="2.0",
            width=80,
        )

        self.active_ref_field = ft.TextField(
            value="Aucune référence chargée",
            read_only=True,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
        )

        self.save_btn = ft.ElevatedButton(
            "💾 Enregistrer un nouveau câble",
            on_click=lambda _: self.on_save_clicked(),
            width=280,
            height=40,
            disabled=True
        )

        self.test_btn = ft.ElevatedButton(
            "✓ Tester la conformité",
            on_click=lambda _: self.on_test_clicked(),
            width=280,
            height=40,
            disabled=True
        )

        self.status_text = ft.Text("Prêt.", size=11, color=ft.colors.BLUE)

        self.log_view = ft.ListView(
            expand=True,
            spacing=2,
            padding=10,
            auto_scroll=True,
        )

        # ===== SECTION CONFIGURATION UART =====
        uart_section = ft.Container(
            content=ft.Column([
                ft.Text("Configuration UART", size=16, weight=ft.FontWeight.BOLD),

                # Ligne 1: Port
                ft.Row([
                    ft.Text("Port :", size=12, weight=ft.FontWeight.BOLD, width=80),
                    self.port_dropdown,
                    ft.ElevatedButton("🔄 Re-scanner", on_click=lambda _: self.refresh_ports(), width=120),
                    self.identify_btn,
                    self.disconnect_btn,
                ], spacing=10),

                # Ligne 2: Paramètres
                ft.Row([
                    ft.Text("Baudrate :", size=12, weight=ft.FontWeight.BOLD, width=80),
                    self.baud_field,
                    ft.Text("Timeout :", size=12, weight=ft.FontWeight.BOLD),
                    self.timeout_field,
                    ft.Text("secondes", size=10),
                ], spacing=10),
            ], spacing=10),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=10,
        )

        # ===== SECTION RÉFÉRENCE =====
        ref_section = ft.Container(
            content=ft.Column([
                ft.Text("Référence de câblage", size=16, weight=ft.FontWeight.BOLD),

                # Champ référence
                self.active_ref_field,

                # Boutons gestion référence
                ft.Row([
                    ft.ElevatedButton(
                        "📁 Charger une référence",
                        on_click=lambda _: self.load_reference(),
                        width=220
                    ),
                    ft.ElevatedButton(
                        "🗑️ Effacer",
                        on_click=lambda _: self.clear_reference(),
                        width=120
                    ),
                ], spacing=10),
            ], spacing=10),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=10,
        )

        # ===== SECTION ACTIONS =====
        action_section = ft.Container(
            content=ft.Column([
                ft.Text("Actions", size=16, weight=ft.FontWeight.BOLD),

                ft.Row([
                    self.save_btn,
                    self.test_btn,
                ], spacing=15),
            ], spacing=10),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=10,
        )

        # ===== STATUS BAR =====
        status_bar = ft.Row([
            ft.Text("État :", size=11, weight=ft.FontWeight.BOLD),
            self.status_text,
        ], spacing=5)

        # ===== LOG =====
        log_section = ft.Container(
            content=ft.Column([
                ft.Text("📋 Journal d'activité", size=16, weight=ft.FontWeight.BOLD),
                self.log_view,
            ], spacing=10),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=10,
            expand=True,
        )

        # Assemblage de l'interface
        self.page.add(
            ft.Column([
                uart_section,
                ref_section,
                action_section,
                status_bar,
                log_section,
            ], spacing=10, expand=True)
        )

    def log_line(self, s: str):
        """Ajoute une ligne au journal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.controls.append(
            ft.Text(f"[{timestamp}] {s}", size=10, font_family="Courier New")
        )
        self.page.update()

    def set_status(self, s: str):
        """Met à jour le statut"""
        self.status_text.value = s
        self.page.update()

    def refresh_ports(self):
        """Rafraîchit la liste des ports série"""
        # Déconnexion du port actuel si nécessaire
        if self.serial_port is not None:
            self.disconnect_tester()

        ports = list(list_ports.comports())
        items = [p.device for p in ports]

        # Réinitialisation de l'identification
        self.tester_identified = False
        self.save_btn.disabled = True
        self.test_btn.disabled = True

        self.port_dropdown.options = [ft.dropdown.Option(item) for item in items]
        if items:
            if not self.port_dropdown.value or self.port_dropdown.value not in items:
                self.port_dropdown.value = items[0]
            self.set_status(f"{len(items)} port(s) détecté(s). Identification requise.")
        else:
            self.port_dropdown.value = None
            self.set_status("Aucun port détecté.")

        self.page.update()
        self.log_line("Ports détectés : " + (", ".join(items) if items else "(aucun)"))

        # Détection automatique du testeur
        self._auto_detect_tester(ports)

    def _auto_detect_tester(self, ports):
        """Détecte automatiquement le testeur TTL-232R-5V-WE"""
        target_vid = 0x0403
        target_pid = 0x6001

        for port_info in ports:
            if port_info.vid == target_vid and port_info.pid == target_pid:
                device_name = port_info.device
                description = port_info.description if port_info.description else "Inconnu"

                self.log_line(f"✓ Testeur de câbles détecté : {description} sur {device_name}")

                # Créer une dialog de confirmation
                def on_dialog_result(e):
                    dialog.open = False
                    self.page.update()
                    if e.control.text == "Oui":
                        self.port_dropdown.value = device_name
                        self.page.update()
                        self.log_line(f"Connexion automatique au testeur sur {device_name}...")
                        # Petit délai pour l'interface
                        time.sleep(0.1)
                        self.identify_tester()

                dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Testeur de câbles détecté"),
                    content=ft.Text(
                        f"Un testeur de câbles a été détecté :\n\n"
                        f"Port : {device_name}\n"
                        f"Périphérique : {description}\n"
                        f"VID:PID : {port_info.vid:04X}:{port_info.pid:04X}\n\n"
                        f"Voulez-vous vous connecter automatiquement ?"
                    ),
                    actions=[
                        ft.TextButton("Oui", on_click=on_dialog_result),
                        ft.TextButton("Non", on_click=on_dialog_result),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )

                self.page.dialog = dialog
                dialog.open = True
                self.page.update()
                break

    def identify_tester(self):
        """Identifie le testeur"""
        port = (self.port_dropdown.value or "").strip()
        if not port:
            self._show_warning("Port manquant", "Sélectionne un port UART avant d'identifier le testeur.")
            return

        try:
            baud = int((self.baud_field.value or "").strip())
        except ValueError:
            self._show_warning("Baudrate invalide", "Entre un baudrate valide (ex: 38400).")
            return

        self.log_line(f"Tentative d'identification du testeur sur {port}...")
        self.identify_btn.disabled = True
        self.page.update()
        self.set_status("Identification en cours…")

        # Thread pour l'identification
        th = threading.Thread(
            target=self._worker_identify,
            args=(port, baud),
            daemon=True,
        )
        th.start()

    def disconnect_tester(self):
        """Déconnecte le testeur"""
        if self.serial_port is not None:
            try:
                self.serial_port.close()
                self.log_line(f"✓ Déconnexion du port {self.serial_port.port}")
            except Exception as e:
                self.log_line(f"✗ Erreur lors de la déconnexion : {e}")
            finally:
                self.serial_port = None

        # Réinitialisation de l'état
        self.tester_identified = False
        self.save_btn.disabled = True
        self.test_btn.disabled = True
        self.identify_btn.disabled = False
        self.disconnect_btn.disabled = True
        self.set_status("Déconnecté.")
        self.page.update()

    def _worker_identify(self, port, baud):
        """Worker thread pour l'identification du testeur"""
        try:
            id_cmd = b"IDN\n"
            timeout = 0.2

            ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)

            ser.reset_input_buffer()
            ser.reset_output_buffer()
            time.sleep(0.1)

            ser.write(id_cmd)
            ser.flush()

            response_bytes = b""
            start_time = time.time()
            max_wait = 2.0

            while time.time() - start_time < max_wait:
                chunk = ser.read(1024)
                if chunk:
                    response_bytes += chunk
                else:
                    if len(response_bytes) > 0:
                        time.sleep(0.1)
                        final_chunk = ser.read(1024)
                        if final_chunk:
                            response_bytes += final_chunk
                        else:
                            break
                    else:
                        time.sleep(0.05)

            response = response_bytes.decode("utf-8", errors="ignore").strip()

            if "Testeur de cordon" in response:
                self._finish_identify(True, response, ser)
            else:
                ser.close()
                error_msg = f"Réponse invalide : '{response}'" if response else "Aucune réponse"
                self._finish_identify(False, error_msg, None)

        except Exception as e:
            if 'ser' in locals() and ser is not None:
                try:
                    ser.close()
                except:
                    pass
            self._finish_identify(False, str(e), None)

    def _finish_identify(self, success, response, serial_obj):
        """Traite le résultat de l'identification"""
        self.identify_btn.disabled = False

        if success:
            self.serial_port = serial_obj
            self.tester_identified = True
            self.save_btn.disabled = False
            self.test_btn.disabled = False
            self.identify_btn.disabled = True
            self.disconnect_btn.disabled = False
            self.set_status("✓ Testeur connecté et prêt")
            self.log_line(f"✓ Testeur identifié : {response}")
            self.log_line(f"✓ Port {self.serial_port.port} maintenu ouvert pour les opérations suivantes")

            self._show_info(
                "Connexion réussie",
                f"Le testeur est connecté et prêt.\n\nRéponse : {response}\n\nLe port restera ouvert jusqu'à la déconnexion."
            )
        else:
            self.tester_identified = False
            self.serial_port = None
            self.save_btn.disabled = True
            self.test_btn.disabled = True
            self.disconnect_btn.disabled = True
            self.set_status("✗ Échec de connexion")
            self.log_line(f"✗ Échec d'identification : {response}")

            self._show_error(
                "Échec de connexion",
                f"Le testeur n'a pas pu être identifié.\n\nErreur : {response}\n\nVérifiez :\n- Le port est correct\n- Le testeur est allumé\n- Le baudrate est correct"
            )

        self.page.update()

    def load_reference(self):
        """Charge un fichier JSON de référence"""
        def on_dialog_result(e: ft.FilePickerResultEvent):
            if e.files:
                filepath = e.files[0].path
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if not isinstance(data, dict):
                        self._show_error("Erreur", "Le fichier JSON doit contenir un objet/dictionnaire.")
                        return

                    filename = os.path.basename(filepath)
                    self.references[filename] = {"path": filepath, "data": data}
                    self.active_reference = filename
                    self.update_reference_display()

                    self.log_line(f"Référence chargée : {filename}")
                    self.set_status("Prêt.")

                except json.JSONDecodeError as e:
                    self.set_status("Erreur de chargement.")
                    self._show_error("Erreur JSON", f"Impossible de lire le fichier JSON:\n{e}")
                except Exception as e:
                    self.set_status("Erreur de chargement.")
                    self._show_error("Erreur", f"Erreur lors du chargement:\n{e}")

        file_picker = ft.FilePicker(on_result=on_dialog_result)
        self.page.overlay.append(file_picker)
        self.page.update()

        self.set_status("Ouverture du sélecteur de fichiers...")
        file_picker.pick_files(
            dialog_title="Charger une référence JSON",
            initial_directory=self.references_dir,
            allowed_extensions=["json"],
        )

    def clear_reference(self):
        """Efface la référence active"""
        if not self.active_reference:
            self._show_info("Aucune référence", "Il n'y a pas de référence active à effacer.")
            return

        filename = self.active_reference
        filepath = self.references[filename]["path"]

        # Dialog avec checkbox
        def on_dialog_result(e):
            dialog.open = False
            self.page.update()

            if e.control.text == "OK":
                delete_file = checkbox.value

                if delete_file:
                    try:
                        os.remove(filepath)
                        self.log_line(f"✓ Fichier supprimé : {filepath}")
                    except Exception as ex:
                        self.log_line(f"✗ Erreur lors de la suppression du fichier : {ex}")
                        self._show_error("Erreur", f"Impossible de supprimer le fichier :\n{ex}")

                self.active_reference = None
                if filename in self.references:
                    del self.references[filename]

                self.update_reference_display()
                self.log_line(f"Référence effacée : {filename}")

        checkbox = ft.Checkbox(
            label="Supprimer aussi le fichier physique (⚠️ irréversible)",
            value=False
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmer l'effacement"),
            content=ft.Column([
                ft.Text(f"Effacer la référence '{filename}' ?\n\n{filepath}"),
                checkbox,
            ], tight=True),
            actions=[
                ft.TextButton("OK", on_click=on_dialog_result),
                ft.TextButton("Annuler", on_click=on_dialog_result),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def update_reference_display(self):
        """Met à jour l'affichage de la référence active"""
        if self.active_reference and self.active_reference in self.references:
            ref_data = self.references[self.active_reference]
            num_pins = len(ref_data["data"])
            filepath = ref_data["path"]
            parent_dir = os.path.basename(os.path.dirname(filepath))
            self.active_ref_field.value = f"{parent_dir}/{self.active_reference} ({num_pins} pins)"
        else:
            self.active_ref_field.value = "Aucune référence chargée"
        self.page.update()

    def on_test_clicked(self):
        """Lance un test de conformité"""
        if not self.tester_identified:
            self._show_warning("Testeur non identifié", "Identifie d'abord le testeur avec le bouton '🔌 Connecter'.")
            return

        if not self.active_reference or self.active_reference not in self.references:
            self._show_warning("Référence manquante", "Charge ou sélectionne une référence active avant de tester.")
            return

        port = (self.port_dropdown.value or "").strip()
        if not port:
            self._show_warning("Port manquant", "Sélectionne un port UART.")
            return

        try:
            baud = int((self.baud_field.value or "").strip())
        except ValueError:
            self._show_warning("Baudrate invalide", "Entre un baudrate valide (ex: 38400).")
            return

        try:
            timeout = float((self.timeout_field.value or "").strip())
        except ValueError:
            self._show_warning("Timeout invalide", "Entre un timeout valide (ex: 2.0).")
            return

        cmd_text = self.cmd_var
        cmd_bytes = cmd_text.encode("utf-8").decode("unicode_escape").encode("utf-8")

        self.test_btn.disabled = True
        self.save_btn.disabled = True
        self.page.update()
        self.set_status("Test en cours…")
        self.log_line(f"Test de conformité avec {self.active_reference}…")
        self.log_line(f"Ouverture {port} @ {baud}… envoi commande: {cmd_text!r}")

        ref_data = self.references[self.active_reference]["data"]

        th = threading.Thread(
            target=self._worker_test,
            args=(port, baud, timeout, cmd_bytes, ref_data),
            daemon=True,
        )
        th.start()

    def _worker_test(self, port, baud, timeout, cmd_bytes, ref_data):
        """Worker thread pour effectuer le test de conformité"""
        try:
            data = self._run_test_get_json(port, baud, timeout, cmd_bytes)
            is_conform = self._compare_json(ref_data, data)
            self._finish_test(is_conform, data)
        except Exception as e:
            print(e)
            self._finish_test_err(str(e))

    def _compare_json(self, ref_data, test_data):
        """Compare deux dictionnaires JSON"""
        return ref_data == test_data

    def _finish_test(self, is_conform, data):
        """Affiche le résultat du test"""
        self.set_status("Test terminé.")
        self.test_btn.disabled = False
        self.save_btn.disabled = False
        self.page.update()

        if is_conform:
            self.log_line("✓ Test CONFORME : les données correspondent à la référence.")
            self._show_result_popup("CONFORME", ft.colors.GREEN, ft.colors.WHITE)
        else:
            self.log_line("✗ Test NON-CONFORME : les données diffèrent de la référence.")
            self.log_line(f"Données reçues : {json.dumps(data, ensure_ascii=False)[:200]}...")
            self._show_result_popup("NON-CONFORME", ft.colors.RED, ft.colors.WHITE)

    def _finish_test_err(self, msg):
        """Gère les erreurs lors du test"""
        self.log_line("ERREUR lors du test: " + msg)
        self.set_status("Erreur.")
        self.test_btn.disabled = False
        self.save_btn.disabled = False
        self.page.update()
        self._show_error("Erreur de test", msg)

    def _show_result_popup(self, text, bg_color, fg_color):
        """Affiche une popup colorée avec le résultat"""
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            bgcolor=bg_color,
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        text,
                        size=40,
                        weight=ft.FontWeight.BOLD,
                        color=fg_color,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.ElevatedButton(
                        "OK",
                        on_click=close_dialog,
                        width=150,
                        height=45,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20),
                padding=30,
            ),
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

        # Fermeture automatique après 3 secondes
        def auto_close():
            time.sleep(3)
            if dialog.open:
                dialog.open = False
                self.page.update()

        threading.Thread(target=auto_close, daemon=True).start()

    def on_save_clicked(self):
        """Enregistre un nouveau câble"""
        if not self.tester_identified:
            self._show_warning("Testeur non identifié", "Identifie d'abord le testeur avec le bouton '🔌 Connecter'.")
            return

        port = (self.port_dropdown.value or "").strip()
        if not port:
            self._show_warning("Port manquant", "Sélectionne un port UART.")
            return

        try:
            baud = int((self.baud_field.value or "").strip())
        except ValueError:
            self._show_warning("Baudrate invalide", "Entre un baudrate valide (ex: 38400).")
            return

        try:
            timeout = float((self.timeout_field.value or "").strip())
        except ValueError:
            self._show_warning("Timeout invalide", "Entre un timeout valide (ex: 2.0).")
            return

        cmd_text = self.cmd_var
        cmd_bytes = cmd_text.encode("utf-8").decode("unicode_escape").encode("utf-8")

        # File picker pour sauvegarder
        def on_save_result(e: ft.FilePickerResultEvent):
            if e.path:
                filepath = e.path
                if not filepath.endswith('.json'):
                    filepath += '.json'

                self.save_btn.disabled = True
                self.page.update()
                self.set_status("Test en cours…")
                self.log_line(f"Ouverture {port} @ {baud}… envoi commande: {cmd_text!r}")

                th = threading.Thread(
                    target=self._worker_test_and_save,
                    args=(port, baud, timeout, cmd_bytes, filepath),
                    daemon=True,
                )
                th.start()

        file_picker = ft.FilePicker(on_result=on_save_result)
        self.page.overlay.append(file_picker)
        self.page.update()

        file_picker.save_file(
            dialog_title="Enregistrer le brochage",
            file_name="cable.json",
            allowed_extensions=["json"],
        )

    def _worker_test_and_save(self, port, baud, timeout, cmd_bytes, filepath):
        """Worker pour tester et sauvegarder"""
        try:
            data = self._run_test_get_json(port, baud, timeout, cmd_bytes)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self._finish_ok(filepath, data)
        except Exception as e:
            print(e)
            self._finish_err(str(e))

    def _finish_ok(self, filepath, data):
        """Gère la fin de sauvegarde avec succès"""
        self.log_line(f"JSON reçu OK. Sauvegardé : {filepath}")
        self.log_line(f"Contenu (aperçu): {json.dumps(data, ensure_ascii=False)[:200]}...")
        self.set_status("Enregistrement terminé.")
        self.save_btn.disabled = False
        self.page.update()

        # Dialog avec checkbox
        def on_dialog_result(e):
            dialog.open = False
            self.page.update()

            if e.control.text == "OK" and checkbox.value:
                filename = os.path.basename(filepath)
                self.references[filename] = {"path": filepath, "data": data}
                self.active_reference = filename
                self.update_reference_display()
                self.log_line(f"Chargé comme référence active : {filename}")

        checkbox = ft.Checkbox(
            label="Charger comme référence active",
            value=True
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Enregistrement réussi"),
            content=ft.Column([
                ft.Text(f"Brochage enregistré dans :\n{filepath}"),
                checkbox,
            ], tight=True),
            actions=[
                ft.TextButton("OK", on_click=on_dialog_result),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _finish_err(self, msg):
        """Gère les erreurs"""
        self.log_line("ERREUR: " + msg)
        self.set_status("Erreur.")
        self.save_btn.disabled = False
        self.page.update()
        self._show_error("Erreur", msg)

    def _run_test_get_json(self, port, baud, timeout, cmd_bytes):
        """Envoie la commande et lit le JSON"""
        if self.serial_port is None or not self.serial_port.is_open:
            raise RuntimeError("Le port série n'est pas ouvert. Identifiez d'abord le testeur.")

        hard_deadline = time.time() + max(2.0, timeout * 4.0)
        buf = b""

        ser = self.serial_port

        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.05)

        self.log_line(f"Envoi commande: {cmd_bytes}")
        ser.write(cmd_bytes)
        ser.flush()

        time.sleep(0.1)

        while time.time() < hard_deadline:
            chunk = ser.read(4096)
            if chunk:
                buf += chunk
                self.log_line(f"DEBUG: Reçu {len(chunk)} octets: {chunk[:100]}")
                txt = buf.decode("utf-8", errors="ignore")

                start = txt.find("{")
                end = txt.rfind("}")
                if start != -1 and end != -1 and end > start:
                    candidate = txt[start : end + 1].strip()
                    try:
                        obj = json.loads(candidate)
                        if not isinstance(obj, dict):
                            raise ValueError("Le JSON reçu n'est pas un objet/dictionnaire.")
                        return obj
                    except json.JSONDecodeError:
                        pass

        preview = buf.decode("utf-8", errors="ignore")[-300:]
        raise TimeoutError(
            "Timeout: impossible d'obtenir un JSON valide.\n"
            f"Derniers octets reçus (aperçu):\n{preview}"
        )

    def on_closing(self, e):
        """Fermeture propre de l'application"""
        if self.serial_port is not None:
            try:
                self.serial_port.close()
                self.log_line("✓ Port série fermé proprement")
            except:
                pass

    def _show_info(self, title, message):
        """Affiche une boîte de dialogue d'information"""
        def close_dlg(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _show_warning(self, title, message):
        """Affiche une boîte de dialogue d'avertissement"""
        def close_dlg(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _show_error(self, title, message):
        """Affiche une boîte de dialogue d'erreur"""
        def close_dlg(e):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()


def main(page: ft.Page):
    app = CableTesterFletApp(page)


if __name__ == "__main__":
    ft.app(target=main)

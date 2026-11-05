import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:kitchenowl/helpers/named_bytearray.dart';
import 'package:kitchenowl/models/household.dart';
import 'package:kitchenowl/services/api/api_service.dart';

/// Reviews the temporary RecipeLens result. Scanning does not save a recipe.
class RecipeLensUploadPage extends StatefulWidget {
  final Household household;

  const RecipeLensUploadPage({super.key, required this.household});

  @override
  State<RecipeLensUploadPage> createState() => _RecipeLensUploadPageState();
}

class _RecipeLensUploadPageState extends State<RecipeLensUploadPage> {
  bool loading = false;
  String? error;
  String? filename;
  Map<String, dynamic>? result;

  Future<void> scan() async {
    final picked = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['png', 'jpg', 'jpeg', 'pdf'],
    );
    if (picked == null || !mounted) return;
    final bytes = await picked.readAsBytes();
    if (!mounted) return;
    if (bytes.isEmpty || bytes.length > 10 * 1024 * 1024) {
      setState(() => error = 'Choose a nonempty file of at most 10 MB.');
      return;
    }

    setState(() {
      loading = true;
      error = null;
      result = null;
      filename = picked.name;
    });
    try {
      final response = await ApiService.getInstance().postBytes(
        '${ApiService.getInstance().householdPath(widget.household)}/recipe/scan/draft',
        NamedByteArray(picked.name, bytes),
        timeout: const Duration(seconds: 65),
      );
      if (!mounted) return;
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      setState(() {
        if (response.statusCode == 200) {
          result = body;
        } else {
          error =
              body['error']?.toString() ??
              'Scan failed (HTTP ${response.statusCode}).';
        }
      });
    } catch (_) {
      if (mounted)
        setState(() => error = 'Could not scan this file. Try again.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final draft = result?['draft'] as Map<String, dynamic>?;
    final validation = result?['validation'] as Map<String, dynamic>?;
    final warnings = result?['warnings'] as List<dynamic>? ?? const [];
    final errors = validation?['errors'] as List<dynamic>? ?? const [];

    return Scaffold(
      appBar: AppBar(title: const Text('Scan printed recipe')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Text(
                'Upload a PNG, JPEG, or single-page PDF (up to 10 MB).',
              ),
              const SizedBox(height: 12),
              ElevatedButton.icon(
                onPressed: loading ? null : scan,
                icon: const Icon(Icons.upload_file_rounded),
                label: Text(
                  filename == null ? 'Choose recipe file' : 'Scan another file',
                ),
              ),
              if (loading) ...[
                const SizedBox(height: 16),
                const Center(child: CircularProgressIndicator()),
              ],
              if (error != null) ...[
                const SizedBox(height: 16),
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              if (draft != null) ...[
                const SizedBox(height: 24),
                Text(
                  'Review: $filename',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Nothing has been saved. Check the text against your original file.',
                ),
                if (validation?['valid'] == false)
                  const Text('Some required fields were not found.'),
                _field('Title', draft['title']),
                _field('Servings', draft['servings']),
                _field('Prep time (min)', draft['prep_time']),
                _field('Cook time (min)', draft['cook_time']),
                _lines('Ingredients', draft['ingredients']),
                _lines('Instructions', draft['instructions']),
                if (errors.isNotEmpty) _messages('Missing fields', errors),
                if (warnings.isNotEmpty) _messages('Warnings', warnings),
                ExpansionTile(
                  title: const Text('Original recognized text'),
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: SelectableText(
                        result?['source_text']?.toString() ?? '',
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _field(String label, Object? value) => ListTile(
    title: Text(label),
    subtitle: SelectableText(value?.toString() ?? 'Not found'),
  );

  Widget _lines(String label, Object? value) => _field(
    label,
    value is List && value.isNotEmpty ? value.join('\n') : null,
  );

  Widget _messages(String label, List<dynamic> values) => _field(
    label,
    values.map((value) => value is Map ? value['message'] : value).join('\n'),
  );
}

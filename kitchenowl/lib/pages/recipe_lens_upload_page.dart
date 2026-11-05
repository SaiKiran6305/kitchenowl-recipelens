import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:kitchenowl/enums/update_enum.dart';
import 'package:kitchenowl/helpers/named_bytearray.dart';
import 'package:kitchenowl/models/household.dart';
import 'package:kitchenowl/models/item.dart';
import 'package:kitchenowl/models/recipe.dart';
import 'package:kitchenowl/pages/item_search_page.dart';
import 'package:kitchenowl/pages/recipe_add_update_page.dart';
import 'package:kitchenowl/services/api/api_service.dart';

/// OCR is temporary. A recipe is only saved from the existing recipe editor.
class RecipeLensUploadPage extends StatefulWidget {
  final Household household;

  const RecipeLensUploadPage({super.key, required this.household});

  @override
  State<RecipeLensUploadPage> createState() => _RecipeLensUploadPageState();
}

class _RecipeLensUploadPageState extends State<RecipeLensUploadPage> {
  final title = TextEditingController();
  final servings = TextEditingController();
  final prepTime = TextEditingController();
  final cookTime = TextEditingController();
  final ingredients = TextEditingController();
  final instructions = TextEditingController();
  bool loading = false;
  bool matching = false;
  bool suggesting = false;
  int suggestionGeneration = 0;
  final Map<int, Item> suggestedItems = {};
  String? error;
  String? filename;
  Map<String, dynamic>? result;
  List<String> ingredientLines = [];
  final Map<int, RecipeItem> matchedItems = {};

  @override
  void dispose() {
    for (final controller in [
      title,
      servings,
      prepTime,
      cookTime,
      ingredients,
      instructions,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

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
      matching = false;
      error = null;
      result = null;
      filename = picked.name;
      matchedItems.clear();
      suggestedItems.clear();
      suggestionGeneration++;
    });
    try {
      final response = await ApiService.getInstance().postBytes(
        '${ApiService.getInstance().householdPath(widget.household)}/recipe/scan/draft',
        NamedByteArray(picked.name, bytes),
        timeout: const Duration(seconds: 65),
      );
      if (!mounted) return;
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode != 200) {
        setState(
          () => error =
              body['error']?.toString() ??
              'Scan failed (HTTP ${response.statusCode}).',
        );
        return;
      }
      final draft = body['draft'] as Map<String, dynamic>;
      title.text = draft['title']?.toString() ?? '';
      servings.text = draft['servings']?.toString() ?? '';
      prepTime.text = draft['prep_time']?.toString() ?? '';
      cookTime.text = draft['cook_time']?.toString() ?? '';
      ingredients.text = (draft['ingredients'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .join('\n');
      instructions.text = (draft['instructions'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .join('\n');
      setState(() => result = body);
    } catch (_) {
      if (mounted)
        setState(() => error = 'Could not scan this file. Try again.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  int? _number(
    TextEditingController controller,
    String label, {
    int max = 10080,
  }) {
    final raw = controller.text.trim();
    if (raw.isEmpty) return 0;
    final value = int.tryParse(raw);
    if (value == null || value < 0 || value > max) {
      throw FormatException('$label must be a whole number from 0 to $max.');
    }
    return value;
  }

  String _ingredientName(String line) {
    return line
        .trim()
        .toLowerCase()
        .replaceFirst(RegExp(r'^\d+(?:[.,/]\d+)?\s*'), '')
        .replaceFirst(
          RegExp(
            r'^(?:g|kg|ml|l|oz|lb|cups?|tbsp|tsp|tablespoons?|teaspoons?|slices?|cloves?|cans?|pieces?)\b\.?\s*',
          ),
          '',
        )
        .trim();
  }

  String _matchKey(String name) =>
      name.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]+'), ' ').trim();

  Future<void> _suggestIngredients(int generation) async {
    for (var i = 0; i < ingredientLines.length; i++) {
      final query = _ingredientName(ingredientLines[i]);
      if (query.isEmpty) continue;
      try {
        final results =
            await ApiService.getInstance().searchItem(
              widget.household,
              query,
            ) ??
            [];
        if (!mounted || generation != suggestionGeneration) return;
        if (matchedItems.containsKey(i)) continue;
        final exact = results
            .where(
              (item) =>
                  item.id != null && _matchKey(item.name) == _matchKey(query),
            )
            .toList();
        if (exact.length == 1) {
          matchedItems[i] = RecipeItem.fromItem(
            item: exact.first,
          ).copyWith(description: ingredientLines[i]);
        } else if (results.isNotEmpty) {
          suggestedItems[i] = results.first;
        }
        setState(() {});
      } catch (_) {
        // Search failures leave the line available for manual matching.
      }
    }
    if (mounted && generation == suggestionGeneration) {
      setState(() => suggesting = false);
    }
  }

  void reviewIngredients() {
    try {
      if (title.text.trim().isEmpty || title.text.trim().length > 128) {
        throw const FormatException('Enter a title of at most 128 characters.');
      }
      if (instructions.text.trim().isEmpty) {
        throw const FormatException('Enter at least one instruction.');
      }
      _number(servings, 'Servings', max: 1000);
      _number(prepTime, 'Prep time');
      _number(cookTime, 'Cook time');
      final lines = ingredients.text
          .split('\n')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
      if (lines.isEmpty) {
        throw const FormatException('Enter at least one ingredient.');
      }
      final generation = ++suggestionGeneration;
      setState(() {
        ingredientLines = lines;
        matchedItems.clear();
        suggestedItems.clear();
        matching = true;
        suggesting = true;
        error = null;
      });
      _suggestIngredients(generation);
    } on FormatException catch (e) {
      setState(() => error = e.message);
    }
  }

  Future<void> selectIngredient(int index) async {
    final selected = await Navigator.of(context).push<List<Item>>(
      MaterialPageRoute(
        builder: (context) => ItemSearchPage(
          household: widget.household,
          multiple: false,
          title: ingredientLines[index],
          selectedItems: matchedItems[index] == null
              ? []
              : [matchedItems[index]!],
        ),
      ),
    );
    if (!mounted || selected == null || selected.length != 1) return;
    setState(() {
      matchedItems[index] = RecipeItem.fromItem(
        item: selected.first,
      ).copyWith(description: ingredientLines[index]);
      suggestedItems.remove(index);
    });
  }

  Future<void> openRecipeEditor() async {
    if (matchedItems.length != ingredientLines.length) {
      setState(() => error = 'Match every ingredient before continuing.');
      return;
    }
    final prep = _number(prepTime, 'Prep time')!;
    final cook = _number(cookTime, 'Cook time')!;
    final recipe = Recipe(
      name: title.text.trim(),
      description: instructions.text.trim(),
      yields: _number(servings, 'Servings', max: 1000)!,
      prepTime: prep,
      cookTime: cook,
      time: prep + cook,
      items: [
        for (var i = 0; i < ingredientLines.length; i++) matchedItems[i]!,
      ],
    );
    final saved = await Navigator.of(context).push<UpdateEnum>(
      MaterialPageRoute(
        builder: (context) => AddUpdateRecipePage(
          household: widget.household,
          recipe: recipe,
          canSaveWithoutChanges: true,
        ),
      ),
    );
    if (mounted && saved == UpdateEnum.updated) {
      Navigator.of(context).pop(UpdateEnum.updated);
    }
  }

  @override
  Widget build(BuildContext context) {
    final warnings = result?['warnings'] as List<dynamic>? ?? const [];
    return Scaffold(
      appBar: AppBar(
        title: Text(matching ? 'Match ingredients' : 'Scan printed recipe'),
        leading: matching
            ? BackButton(
                onPressed: () => setState(() {
                  matching = false;
                  error = null;
                }),
              )
            : null,
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: matching
                ? _matchingWidgets()
                : [
                    const Text(
                      'Upload a PNG, JPEG, or single-page PDF (up to 10 MB).',
                    ),
                    const SizedBox(height: 12),
                    ElevatedButton.icon(
                      onPressed: loading ? null : scan,
                      icon: const Icon(Icons.upload_file_rounded),
                      label: Text(
                        filename == null
                            ? 'Choose recipe file'
                            : 'Scan another file',
                      ),
                    ),
                    if (loading) ...[
                      const SizedBox(height: 16),
                      const Center(child: CircularProgressIndicator()),
                    ],
                    if (error != null) _error(context),
                    if (result != null) ...[
                      const SizedBox(height: 24),
                      Text(
                        'Review: $filename',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const Text(
                        'Review and correct the OCR result before saving.',
                      ),
                      const SizedBox(height: 12),
                      _input(title, 'Title'),
                      _input(servings, 'Servings', number: true),
                      _input(prepTime, 'Prep time (minutes)', number: true),
                      _input(cookTime, 'Cook time (minutes)', number: true),
                      _input(
                        ingredients,
                        'Ingredients (one per line)',
                        lines: 6,
                      ),
                      _input(
                        instructions,
                        'Instructions (one step per line)',
                        lines: 6,
                      ),
                      if (warnings.isNotEmpty)
                        ListTile(
                          title: const Text('OCR warnings'),
                          subtitle: Text(
                            warnings
                                .map((w) => w is Map ? w['message'] : w)
                                .join('\n'),
                          ),
                        ),
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
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: reviewIngredients,
                        child: const Text('Next: match ingredients'),
                      ),
                    ],
                  ],
          ),
        ),
      ),
    );
  }

  List<Widget> _matchingWidgets() => [
    const Text(
      'Clear matches are filled automatically. Review any unmatched ingredient. Tap a match to change it; the original quantity is kept.',
    ),
    if (suggesting) const LinearProgressIndicator(),
    const SizedBox(height: 16),
    for (var i = 0; i < ingredientLines.length; i++)
      ListTile(
        title: Text(ingredientLines[i]),
        subtitle: Text(
          matchedItems[i]?.name ??
              (suggestedItems[i] == null
                  ? 'Choose item'
                  : 'Suggested: ${suggestedItems[i]!.name} — tap to confirm'),
        ),
        trailing: IconButton(
          icon: Icon(
            matchedItems[i] == null ? Icons.search_rounded : Icons.edit_rounded,
          ),
          tooltip: 'Search for another item',
          onPressed: () => selectIngredient(i),
        ),
        onTap: () {
          final suggestion = suggestedItems[i];
          if (matchedItems[i] != null || suggestion == null) {
            selectIngredient(i);
          } else {
            setState(() {
              matchedItems[i] = RecipeItem.fromItem(
                item: suggestion,
              ).copyWith(description: ingredientLines[i]);
              suggestedItems.remove(i);
            });
          }
        },
      ),
    if (error != null) _error(context),
    const SizedBox(height: 16),
    ElevatedButton(
      onPressed: !suggesting && matchedItems.length == ingredientLines.length
          ? openRecipeEditor
          : null,
      child: const Text('Continue to recipe editor'),
    ),
    const Text('Nothing is saved until you press Add recipe in the editor.'),
  ];

  Widget _error(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Text(
      error!,
      style: TextStyle(color: Theme.of(context).colorScheme.error),
    ),
  );

  Widget _input(
    TextEditingController controller,
    String label, {
    bool number = false,
    int lines = 1,
  }) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: TextField(
      controller: controller,
      keyboardType: number ? TextInputType.number : TextInputType.multiline,
      maxLines: lines,
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    ),
  );
}

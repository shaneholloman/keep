import { Button } from "@/components/ui";
import { useConfig } from "@/utils/hooks/useConfig";
import {
  useCopilotAction,
  useCopilotContext,
  useCopilotReadable,
} from "@copilotkit/react-core";
import { CopilotTask } from "@copilotkit/react-core";
import { Subtitle, TextInput, Select, SelectItem } from "@tremor/react";
import { useCallback, useState } from "react";
import { PresetControls } from "./preset-controls";
import CreatableMultiSelect from "@/components/ui/CreatableMultiSelect";
import { AlertsCountBadge } from "./alerts-count-badge";
import { TbSparkles } from "react-icons/tb";
import { MultiValue } from "react-select";
import { useTags } from "@/utils/hooks/useTags";
import { Preset } from "@/entities/presets/model/types";
import { usePresetActions } from "@/entities/presets/model/usePresetActions";

interface TagOption {
  id?: string;
  name: string;
}

type CreateOrUpdatePresetFormProps = {
  presetId: string | null;
  presetData: {
    CEL: string;
    name: string | undefined;
    isPrivate: boolean | undefined;
    isNoisy: boolean | undefined;
    counterShowsFiringOnly: boolean | undefined;
    tags: TagOption[] | undefined;
    groupColumn: string | undefined;
  };
  groupableColumns: { id: string; header: string }[];
  onCreateOrUpdate?: (preset: Preset) => void;
  onCancel?: () => void;
};

export function CreateOrUpdatePresetForm({
  presetId,
  presetData,
  groupableColumns,
  onCreateOrUpdate,
  onCancel,
}: CreateOrUpdatePresetFormProps) {
  const [presetName, setPresetName] = useState(presetData.name ?? "");
  const [isPrivate, setIsPrivate] = useState(presetData.isPrivate ?? false);
  const [isNoisy, setIsNoisy] = useState(presetData.isNoisy ?? false);
  const [counterShowsFiringOnly, setCounterShowsFiringOnly] = useState(
    presetData.counterShowsFiringOnly ?? true
  );

  const [groupColumn, setGroupColumn] = useState(presetData.groupColumn ?? "");

  const [generatingName, setGeneratingName] = useState(false);
  const [selectedTags, setSelectedTags] = useState<TagOption[]>(
    presetData.tags ?? []
  );

  const clearForm = () => {
    setPresetName("");
    setIsPrivate(false);
    setIsNoisy(false);
    setSelectedTags([]);
    setCounterShowsFiringOnly(true);
  };

  const handleCancel = () => {
    clearForm();
    onCancel?.();
  };

  const { data: tags = [] } = useTags();

  const handleCreateTag = (inputValue: string) => {
    const newTag = { name: inputValue };
    setSelectedTags((prevTags) => [...prevTags, newTag]);
  };

  const handleChange = (
    newValue: MultiValue<{ value: string; label: string }>
  ) => {
    setSelectedTags(
      newValue.map((tag) => ({
        id: tags.find((t) => t.name === tag.value)?.id,
        name: tag.value,
      }))
    );
  };

  const { data: configData } = useConfig();
  const isAIEnabled = configData?.OPEN_AI_API_KEY_SET;
  const context = useCopilotContext();

  useCopilotReadable({
    description: "The CEL query for the alert preset",
    value: presetData.CEL,
  });

  useCopilotAction({
    name: "setGeneratedName",
    description: "Set the generated preset name",
    parameters: [
      { name: "name", type: "string", description: "The generated name" },
    ],
    handler: async ({ name }) => {
      setPresetName(name);
    },
  });

  const generatePresetName = useCallback(async () => {
    setGeneratingName(true);
    const task = new CopilotTask({
      instructions:
        "Generate a short, descriptive name for an alert preset based on the provided CEL query. The name should be concise but meaningful, reflecting the key conditions in the query.",
    });
    await task.run(context);
    setGeneratingName(false);
  }, [context]);

  const { createPreset, updatePreset } = usePresetActions();
  const addOrUpdatePreset = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (presetId) {
      const updatedPreset = await updatePreset(presetId, {
        ...presetData,
        name: presetName,
        isPrivate,
        isNoisy,
        counterShowsFiringOnly,
        tags: selectedTags.map((tag) => ({
          id: tag.id,
          name: tag.name,
        })),
      });
      onCreateOrUpdate?.(updatedPreset);
    } else {
      const newPreset = await createPreset({
        ...presetData,
        name: presetName,
        isPrivate,
        isNoisy,
        counterShowsFiringOnly,
        tags: selectedTags.map((tag) => ({
          id: tag.id,
          name: tag.name,
        })),
      });
      onCreateOrUpdate?.(newPreset);
    }
  };

  return (
    <form
      data-testid="preset-form"
      className="space-y-2"
      onSubmit={addOrUpdatePreset}
    >
      <div className="text-lg font-semibold">
        <p>{presetName ? "Update preset" : "Enter new preset name"}</p>
      </div>

      <div className="space-y-2">
        <Subtitle>Preset Name</Subtitle>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <TextInput
              data-testid="preset-name-input"
              // TODO: don't show error until user tries to save
              error={!presetName}
              errorMessage="Preset name is required"
              placeholder={
                presetName === "feed" || presetName === "deleted"
                  ? ""
                  : presetName
              }
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              className="w-full"
            />
            {isAIEnabled && (
              <Button
                variant="secondary"
                onClick={generatePresetName}
                disabled={!presetData.CEL || generatingName}
                loading={generatingName}
                icon={TbSparkles}
                size="xs"
              >
                AI
              </Button>
            )}
          </div>
        </div>
        <PresetControls
          isPrivate={isPrivate}
          setIsPrivate={setIsPrivate}
          isNoisy={isNoisy}
          setIsNoisy={setIsNoisy}
          counterShowsFiringOnly={counterShowsFiringOnly}
          setCounterShowsFiringOnly={setCounterShowsFiringOnly}
        />
      </div>
      {/* Group by column TODO
        <div className="space-y-2">
          <Subtitle>Group By Column</Subtitle>
          <Select
            value={groupColumn}
            onValueChange={setGroupColumn}
            placeholder="Select a column to group by"
          >
            <SelectItem value="">None</SelectItem>
            {groupableColumns.map((column) => (
              <SelectItem key={column.id} value={column.id}>
                {column.header}
              </SelectItem>
            ))}
          </Select>
        </div>
      */}

      <Subtitle>Tags</Subtitle>
      <CreatableMultiSelect
        value={selectedTags.map((tag) => ({
          value: tag.name,
          label: tag.name,
        }))}
        onChange={handleChange}
        onCreateOption={handleCreateTag}
        options={tags.map((tag) => ({
          value: tag.name,
          label: tag.name,
        }))}
        placeholder="Select or create tags"
      />

      {/* Add alerts count card before the save buttons */}
      {presetData.CEL && (
        <AlertsCountBadge
          presetCEL={presetData.CEL}
          isDebouncing={false}
          vertical={true}
          description="These are the alerts that would match your preset"
        />
      )}

      <div className="flex justify-end space-x-2.5">
        <Button
          type="button"
          size="lg"
          variant="secondary"
          color="orange"
          onClick={handleCancel}
          tooltip="Close"
        >
          Close
        </Button>
        <Button
          data-testid="save-preset-button"
          disabled={!presetName}
          type="submit"
          size="lg"
          color="orange"
          variant="primary"
          tooltip="Save Preset"
        >
          Save
        </Button>
      </div>
    </form>
  );
}

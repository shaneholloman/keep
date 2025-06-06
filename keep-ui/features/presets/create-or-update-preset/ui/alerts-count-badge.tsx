// TODO: move models to entities/alerts
import { useAlerts } from "@/entities/alerts/model/useAlerts";
import { Badge, Card, Text } from "@tremor/react";

interface AlertsCountBadgeProps {
  presetCEL: string;
  isDebouncing: boolean;
  vertical?: boolean;
  description?: string;
}

export const AlertsCountBadge: React.FC<AlertsCountBadgeProps> = ({
  presetCEL,
  isDebouncing,
  vertical = false,
  description,
}) => {
  console.log("AlertsCountBadge::presetCEL", presetCEL);
  const { useLastAlerts } = useAlerts();
  const { totalCount, isLoading: isSearching } = useLastAlerts({
    cel: presetCEL,
    limit: 20,
    offset: 0,
  });

  console.log("AlertsCountBadge::swr", totalCount);

  // Show loading state when searching or debouncing
  if (isSearching || isDebouncing) {
    return (
      <Card className="px-2 py-3">
        <div className="flex justify-center">
          <div
            className={`flex ${
              vertical ? "flex-col" : "flex-row"
            } items-center gap-2`}
          >
            <Badge size="xl" color="orange">
              ...
            </Badge>
            <Text className="text-sm">Searching...</Text>
          </div>
        </div>
      </Card>
    );
  }

  // Don't show anything if there's no data
  if (!Number.isInteger(totalCount)) {
    return null;
  }

  return (
    <Card className="px-2 py-3">
      <div className="flex justify-center">
        <div
          className={`flex ${
            vertical ? "flex-col" : "flex-row"
          } items-center gap-2`}
        >
          <Badge data-testid="alerts-count-badge" size="xl" color="orange">
            {totalCount}
          </Badge>
          <Text className="text-sm">
            {totalCount === 1 ? "Alert" : "Alerts"} found
          </Text>
        </div>
      </div>
      {description && (
        <Text className="text-center text-gray-500 mt-2">{description}</Text>
      )}
    </Card>
  );
};

"""
Statuscake is a class that provides a way to read alerts from the Statuscake API and install webhook in StatuCake
"""

import dataclasses
from typing import List
from urllib.parse import urlencode, urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class StatuscakeProviderAuthConfig:
    """
    StatuscakeProviderAuthConfig is a class that holds the authentication information for the StatuscakeProvider.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Statuscake API Key",
            "sensitive": True,
        },
        default=None,
    )


class StatuscakeProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Statuscake"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts",
            description="Read alerts from Statuscake",
        )
    ]

    SEVERITIES_MAP = {
        "high": AlertSeverity.HIGH,
    }

    STATUS_MAP = {
        "Up": AlertStatus.RESOLVED,
        "Down": AlertStatus.FIRING,
    }

    FINGERPRINT_FIELDS = ["test_id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for StatucCake api requests.
        """
        host = "https://api.statuscake.com/v1/"
        url = urljoin(
            host,
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"
        return url

    def validate_scopes(self):
        """
        Validate that the user has the required scopes to use the provider
        """
        self.logger.info("Validating scopes for Statuscake provider")
        try:
            response = requests.get(
                url=self.__get_url(paths=["uptime"]),
                headers=self.__get_auth_headers(),
            )

            if response.status_code == 200:
                self.logger.info("Successfully validated scopes for Statuscake")
                scopes = {"alerts": True}

            else:
                self.logger.error(
                    "Unable to read alerts from Statuscake, statusCode: %s",
                    response.status_code,
                )
                scopes = {
                    "alerts": f"Unable to read alerts from Statuscake, statusCode: {response.status_code}"
                }

        except Exception as e:
            self.logger.error("Error validating scopes for Statuscake: %s", e)
            scopes = {"alerts": f"Error validating scopes for Statuscake: {e}"}

        return scopes

    def validate_config(self):
        self.logger.info("Validating configuration for Statuscake provider")
        self.authentication_config = StatuscakeProviderAuthConfig(
            **self.config.authentication
        )
        if self.authentication_config.api_key is None:
            self.logger.error("Statuscake API Key is missing")
            raise ValueError("Statuscake API Key is required")
        self.logger.info("Configuration validated successfully")

    def __get_auth_headers(self):
        if self.authentication_config.api_key is not None:
            return {
                "Authorization": f"Bearer {self.authentication_config.api_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

    def __get_paginated_data(self, paths: list, query_params: dict = {}):
        data = []
        try:
            page = 1
            while True:
                self.logger.info(f"Getting page: {page} for {paths}")
                response = requests.get(
                    url=self.__get_url(
                        paths=paths, query_params={**query_params, "page": page}
                    ),
                    headers=self.__get_auth_headers(),
                )

                if not response.ok:
                    raise Exception(response.text)

                response = response.json()
                data.extend(response["data"])
                if page == response["metadata"]["page_count"]:
                    break
                else:
                    page += 1
            self.logger.info(
                f"Successfully got {len(data)} items from {paths}",
                extra={"data": data},
            )
            return data

        except Exception as e:
            self.logger.error(
                f"Error while getting {paths}", extra={"exception": str(e)}
            )
            raise e

    def __update_contact_group(self, contact_group_id, keep_api_url):
        try:
            self.logger.info(f"Updating contact group {contact_group_id}")
            response = requests.put(
                url=self.__get_url(["contact-groups", contact_group_id]),
                headers=self.__get_auth_headers(),
                data={
                    "ping_url": keep_api_url,
                },
            )
            if response.status_code != 204:
                raise Exception(response.text)
            self.logger.info(f"Successfully updated contact group {contact_group_id}")
        except Exception as e:
            self.logger.error(
                "Error while updating contact group", extra={"exception": str(e)}
            )
            raise e

    def __create_contact_group(self, keep_api_url: str, contact_group_name: str):
        try:
            self.logger.info(f"Creating contact group: {contact_group_name}")
            response = requests.post(
                url=self.__get_url(paths=["contact-groups"]),
                headers=self.__get_auth_headers(),
                data={
                    "ping_url": keep_api_url,
                    "name": contact_group_name,
                },
            )
            if response.status_code != 201:
                raise Exception(response.text)
            self.logger.info("Successfully created contact group")
            return response.json()["data"]["new_id"]
        except Exception as e:
            self.logger.error(
                "Error while creating contact group", extra={"exception": str(e)}
            )
            raise e

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        # Getting all the contact groups
        self.logger.info("Attempting to install webhook in statuscake")
        keep_api_url = f"{keep_api_url}&api_key={api_key}"
        contact_group_name = f"Keep-{self.provider_id}"
        self.logger.info("Getting contact groups for webhook setup")
        contact_groups = self.__get_paginated_data(paths=["contact-groups"])

        for contact_group in contact_groups:
            if contact_group["name"] == contact_group_name:
                self.logger.info(
                    "Webhook already exists, updating the ping_url, just for safe measures"
                )
                contact_group_id = contact_group["id"]
                self.__update_contact_group(
                    contact_group_id=contact_group_id, keep_api_url=keep_api_url
                )
                break
        else:
            self.logger.info("Creating a new contact group")
            contact_group_id = self.__create_contact_group(
                contact_group_name=contact_group_name, keep_api_url=keep_api_url
            )

        alerts_to_update = ["heartbeat", "uptime", "pagespeed", "ssl"]
        self.logger.info(f"Updating alerts for types: {alerts_to_update}")

        for alert_type in alerts_to_update:
            self.logger.info(f"Processing {alert_type} alerts")
            alerts = self.__get_paginated_data(paths=[alert_type])
            for alert in alerts:
                if contact_group_id not in alert["contact_groups"]:
                    alert["contact_groups"].append(contact_group_id)
                    try:
                        self.__update_alert(
                            data={"contact_groups[]": alert["contact_groups"]},
                            paths=[alert_type, alert["id"]],
                        )
                    except Exception:
                        self.logger.exception(
                            "Error while updating alert",
                            extra={
                                "alert_type": alert_type,
                                "alert_id": alert.get("id"),
                            },
                        )

        self.logger.info("Webhook setup completed successfully")

    def __update_alert(self, data: dict, paths: list):
        try:
            self.logger.info(f"Attempting to updated alert: {paths}")
            response = requests.put(
                url=self.__get_url(paths=paths),
                headers=self.__get_auth_headers(),
                data=data,
            )
            if not response.ok:
                self.logger.error(
                    "Error while updating alert",
                    extra={"response": response.text, "data": data, "paths": paths},
                )
                # best effort
                pass
            else:
                self.logger.info(
                    "Successfully updated alert", extra={"data": data, "paths": paths}
                )
        except Exception as e:
            self.logger.error("Error while updating alert", extra={"exception": str(e)})
            raise e

    def __get_heartbeat_alerts_dto(self) -> list[AlertDto]:
        self.logger.info("Getting heartbeat alerts from Statuscake")
        response = self.__get_paginated_data(paths=["heartbeat"])

        alert_dtos = [
            AlertDto(
                id=alert["id"],
                name=alert["name"],
                status=alert["status"],
                url=alert["website_url"],
                uptime=alert["uptime"],
                source="statuscake",
            )
            for alert in response
        ]
        self.logger.info(f"Got {len(alert_dtos)} heartbeat alerts")
        return alert_dtos

    def __get_pagespeed_alerts_dto(self) -> list[AlertDto]:
        self.logger.info("Getting pagespeed alerts from Statuscake")
        response = self.__get_paginated_data(paths=["pagespeed"])

        alert_dtos = []
        for alert in response:
            status = alert.get("latest_stats", {}).get("has_issues", False)
            if status:
                status = AlertStatus.FIRING
            else:
                status = AlertStatus.RESOLVED

            alert_dto = AlertDto(
                name=alert["name"],
                url=alert["website_url"],
                location=alert["location"],
                alert_smaller=alert["alert_smaller"],
                alert_bigger=alert["alert_bigger"],
                alert_slower=alert["alert_slower"],
                status=status,
                source=["statuscake"],
                latest_stats=alert.get("latest_stats", {}),
                fingerprint=alert.get("id"),
            )
            alert_dtos.append(alert_dto)
        self.logger.info(f"Got {len(alert_dtos)} pagespeed alerts")
        return alert_dtos

    def __get_ssl_alerts_dto(self) -> list[AlertDto]:
        self.logger.info("Getting SSL alerts from Statuscake")
        response = self.__get_paginated_data(paths=["ssl"])
        alert_dtos = []
        self.logger.info(f"Got {len(response)} ssl alerts")
        for alert in response:
            url = alert.get("website_url", None)
            alert_dto = AlertDto(
                name=f"Certificate for {url}",
                **alert,
                source=["statuscake"],
            )
            alert_dtos.append(alert_dto)
        return alert_dtos

    def __get_uptime_alerts_dto(self) -> list[AlertDto]:
        self.logger.info("Getting uptime alerts from Statuscake")
        response = self.__get_paginated_data(paths=["uptime"])

        self.logger.info(f"Got {len(response)} uptime alerts")

        alert_dtos = []
        for alert in response:

            if alert.get("status").lower() == "up":
                status = AlertStatus.RESOLVED
            else:
                status = AlertStatus.FIRING

            alert_id = alert.get("id", None)
            if not alert_id:
                self.logger.error("Alert id is missing", extra={"alert": alert})
                continue

            url = alert.get("website_url", None)

            alert = AlertDto(
                id=alert.get("id", ""),
                name=alert.get("name", ""),
                status=status,
                uptime=alert.get("uptime", 0),
                source=["statuscake"],
                paused=alert.get("paused", False),
                test_type=alert.get("test_type", ""),
                check_rate=alert.get("check_rate", 0),
                contact_groups=alert.get("contact_groups", []),
                tags=alert.get("tags", []),
            )
            if url:
                alert.url = url
            # use id as fingerprint
            alert.fingerprint = alert_id
            alert_dtos.append(alert)
        return alert_dtos

    def _get_alerts(self) -> list[AlertDto]:
        self.logger.info("Starting to collect all alerts from Statuscake")
        alerts = []
        try:
            self.logger.info("Collecting alerts (heartbeats) from Statuscake")
            heartbeat_alerts = self.__get_heartbeat_alerts_dto()
            alerts.extend(heartbeat_alerts)
        except Exception as e:
            self.logger.error("Error getting heartbeat from Statuscake: %s", e)

        try:
            self.logger.info("Collecting alerts (pagespeed) from Statuscake")
            pagespeed_alerts = self.__get_pagespeed_alerts_dto()
            alerts.extend(pagespeed_alerts)
        except Exception as e:
            self.logger.error("Error getting pagespeed from Statuscake: %s", e)

        try:
            self.logger.info("Collecting alerts (ssl) from Statuscake")
            ssl_alerts = self.__get_ssl_alerts_dto()
            alerts.extend(ssl_alerts)
        except Exception as e:
            self.logger.error("Error getting ssl from Statuscake: %s", e)

        try:
            self.logger.info("Collecting alerts (uptime) from Statuscake")
            uptime_alerts = self.__get_uptime_alerts_dto()
            alerts.extend(uptime_alerts)
        except Exception as e:
            self.logger.error("Error getting uptime from Statuscake: %s", e)

        self.logger.info(
            f"Successfully collected {len(alerts)} total alerts from Statuscake"
        )
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # https://www.statuscake.com/kb/knowledge-base/how-to-use-the-web-hook-url/
        status = StatuscakeProvider.STATUS_MAP.get(
            event.get("Status"), AlertStatus.FIRING
        )

        # Statuscake does not provide severity information
        severity = AlertSeverity.HIGH

        alert = AlertDto(
            id=event.get("TestID", event.get("Name")),
            name=event.get("Name"),
            status=status if status is not None else AlertStatus.FIRING,
            severity=severity,
            url=event.get("URL", None),
            ip=event.get("IP", None),
            tags=event.get("Tags", None),
            test_id=event.get("TestID", None),
            method=event.get("Method", None),
            checkrate=event.get("Checkrate", None),
            status_code=event.get("StatusCode", None),
            source=["statuscake"],
        )
        alert.fingerprint = (
            StatuscakeProvider.get_alert_fingerprint(
                alert,
                (StatuscakeProvider.FINGERPRINT_FIELDS),
            )
            if event.get("TestID", None)
            else None
        )

        return alert


if __name__ == "__main__":
    pass
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    statuscake_api_key = os.environ.get("STATUSCAKE_API_KEY")

    if statuscake_api_key is None:
        raise Exception("STATUSCAKE_API_KEY is required")

    config = ProviderConfig(
        description="Statuscake Provider",
        authentication={"api_key": statuscake_api_key},
    )

    provider = StatuscakeProvider(
        context_manager,
        provider_id="statuscake",
        config=config,
    )
    provider.setup_webhook(
        tenant_id="singletenant",
        keep_api_url="http://localhost:8000/api/v1/alert",
        api_key="test_api_key",
    )
    provider._get_alerts()

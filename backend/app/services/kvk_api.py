"""
KVK (Kamer van Koophandel) API integration for Dutch company data.
"""
import os
from typing import Dict, Any, Optional
import httpx


class KVKApi:
    """Official Dutch company data from KVK API."""
    
    BASE_URL = "https://api.kvk.nl/api/v1"
    
    def __init__(self):
        """Initialize KVK API client."""
        self.api_key = os.getenv("KVK_API_KEY")
        self.enabled = bool(self.api_key)
    
    async def search_company(
        self,
        company_name: str,
        city: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for Dutch company in KVK register.
        
        Args:
            company_name: Name of the company
            city: Optional city to narrow down search
            
        Returns:
            Dictionary with KVK data or None if not found
        """
        if not self.api_key:
            return {
                "source": "kvk",
                "success": False,
                "error": "KVK_API_KEY not configured"
            }
        
        try:
            async with httpx.AsyncClient() as client:
                # Build search parameters
                params = {
                    "naam": company_name,
                    "type": "hoofdvestiging"  # Main establishment
                }
                
                if city:
                    params["plaats"] = city
                
                # Search KVK
                response = await client.get(
                    f"{self.BASE_URL}/zoeken",
                    params=params,
                    headers={
                        "apikey": self.api_key,
                        "Accept": "application/json"
                    },
                    timeout=30.0  # Increased timeout for KVK API
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("resultaten") and len(data["resultaten"]) > 0:
                        # Get first result (most relevant)
                        company = data["resultaten"][0]
                        
                        return {
                            "source": "kvk",
                            "success": True,
                            "data": {
                                "kvk_number": company.get("kvkNummer"),
                                "trade_name": company.get("handelsnaam"),
                                "legal_form": company.get("rechtsvorm"),
                                "address": {
                                    "street": company.get("straatnaam"),
                                    "house_number": company.get("huisnummer"),
                                    "postal_code": company.get("postcode"),
                                    "city": company.get("plaats"),
                                    "country": "Netherlands"
                                },
                                "establishment_date": company.get("startdatum"),
                                "sbi_codes": company.get("sbiCodes", []),  # Industry codes
                                "website": company.get("website"),
                                "employees": company.get("werkzamePersonen")
                            }
                        }
                    else:
                        return {
                            "source": "kvk",
                            "success": False,
                            "error": "Company not found in KVK register"
                        }
                else:
                    return {
                        "source": "kvk",
                        "success": False,
                        "error": f"KVK API returned status {response.status_code}"
                    }
                    
        except httpx.TimeoutException:
            return {
                "source": "kvk",
                "success": False,
                "error": "KVK API timeout"
            }
        except Exception as e:
            return {
                "source": "kvk",
                "success": False,
                "error": f"KVK API error: {str(e)}"
            }
    
    def is_dutch_company(self, country: Optional[str]) -> bool:
        """Check if company is likely Dutch based on country."""
        if not country:
            return False
        
        dutch_indicators = [
            "netherlands",
            "nederland",
            "nl",
            "dutch",
            "holland"
        ]
        
        return country.lower() in dutch_indicators

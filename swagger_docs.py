from flask import Blueprint, jsonify, render_template_string

swagger_bp = Blueprint("swagger_bp", __name__)

SWAGGER_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Recipe Box API",
        "description": "Interactive API testing console and documentation for Recipe Box. Test AI services (recipe suggestion, origin lookup, nutrition analysis) and recipe management endpoints directly from this UI.",
        "version": "1.0.0",
        "contact": {
            "name": "Recipe Box Support"
        }
    },
    "servers": [
        {
            "url": "/",
            "description": "Current Server"
        }
    ],
    "tags": [
        {
            "name": "AI Services",
            "description": "Endpoints powered by Gemini AI for smart recipe assistance"
        },
        {
            "name": "Recipe API",
            "description": "JSON API endpoints for recipe actions"
        },
        {
            "name": "Recipe Web & Actions",
            "description": "Form submission and browsing endpoints"
        }
    ],
    "paths": {
        "/api/recipe/suggest": {
            "post": {
                "tags": ["AI Services"],
                "summary": "Suggest recipe details using AI",
                "description": "Queries Gemini AI to fetch or compose a full recipe (ingredients, instructions, servings, tags) from a dish title. Also checks if a recipe with that title already exists in the box.",
                "operationId": "suggestRecipe",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["title"],
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "example": "Spaghetti Carbonara",
                                        "description": "Title of the recipe to generate"
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Recipe successfully generated",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "example": True},
                                        "recipe": {
                                            "type": "object",
                                            "properties": {
                                                "title": {"type": "string", "example": "Spaghetti Carbonara"},
                                                "instructions": {"type": "string", "example": "1. Cook pasta. 2. Fry guanciale..."},
                                                "servings": {"type": "integer", "example": 4},
                                                "tags": {"type": "string", "example": "italian, pasta, dinner"},
                                                "ingredients": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "amount": {"type": "number", "example": 400},
                                                            "unit": {"type": "string", "example": "g"},
                                                            "name": {"type": "string", "example": "spaghetti"}
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Title missing or empty",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "example": False},
                                        "error": {"type": "string", "example": "Please enter a recipe title first."}
                                    }
                                }
                            }
                        }
                    },
                    "409": {
                        "description": "Recipe already exists in database",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "example": False},
                                        "already_exists": {"type": "boolean", "example": True},
                                        "title": {"type": "string"},
                                        "message": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "500": {
                        "description": "AI generation failed or service temporarily unavailable"
                    }
                }
            }
        },
        "/api/origin/{recipe_id}": {
            "post": {
                "tags": ["AI Services"],
                "summary": "Get cultural origin of a recipe using AI",
                "description": "Retrieves the culinary background and origin story for a recipe using Gemini AI. The result is cached in the database for subsequent requests.",
                "operationId": "getRecipeOrigin",
                "parameters": [
                    {
                        "name": "recipe_id",
                        "in": "path",
                        "required": True,
                        "description": "The ID of the recipe",
                        "schema": {
                            "type": "integer",
                            "example": 1
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Origin text returned",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "example": True},
                                        "origin": {
                                            "type": "string",
                                            "example": "Spaghetti alla Carbonara originates from Rome in the mid-20th century..."
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "404": {"description": "Recipe not found"},
                    "500": {"description": "AI origin lookup error"}
                }
            }
        },
        "/api/nutrition/{recipe_id}": {
            "post": {
                "tags": ["AI Services"],
                "summary": "Estimate nutritional breakdown using AI",
                "description": "Calculates calories, protein, carbs, and fat per serving from the recipe's ingredient list using Gemini AI. Results are cached in the database.",
                "operationId": "getNutritionEstimate",
                "parameters": [
                    {
                        "name": "recipe_id",
                        "in": "path",
                        "required": True,
                        "description": "The ID of the recipe",
                        "schema": {
                            "type": "integer",
                            "example": 1
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Nutrition estimates per serving",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "example": True},
                                        "calories": {"type": "integer", "example": 520},
                                        "protein_g": {"type": "integer", "example": 22},
                                        "carbs_g": {"type": "integer", "example": 65},
                                        "fat_g": {"type": "integer", "example": 18}
                                    }
                                }
                            }
                        }
                    },
                    "400": {"description": "Recipe has no ingredients listed"},
                    "404": {"description": "Recipe not found"},
                    "500": {"description": "AI estimation error"}
                }
            }
        },
        "/api/delete/{recipe_id}": {
            "post": {
                "tags": ["Recipe API"],
                "summary": "Delete a recipe (JSON endpoint)",
                "description": "Deletes the recipe from the database and removes any uploaded image file from storage. Returns JSON result.",
                "operationId": "apiDeleteRecipe",
                "parameters": [
                    {
                        "name": "recipe_id",
                        "in": "path",
                        "required": True,
                        "description": "ID of the recipe to delete",
                        "schema": {
                            "type": "integer",
                            "example": 1
                        }
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Recipe successfully deleted",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean", "example": True},
                                        "id": {"type": "integer", "example": 1}
                                    }
                                }
                            }
                        }
                    },
                    "404": {"description": "Recipe not found"}
                }
            }
        },
        "/": {
            "get": {
                "tags": ["Recipe Web & Actions"],
                "summary": "List recipes / Search",
                "description": "Renders the home page with recipe cards, search by keyword, filter by tag, filter favorites, and pagination.",
                "operationId": "listRecipes",
                "parameters": [
                    {
                        "name": "q",
                        "in": "query",
                        "description": "Search keyword (matches title, instructions, ingredients, or tags)",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "tag",
                        "in": "query",
                        "description": "Filter by tag name",
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "favorites",
                        "in": "query",
                        "description": "Pass '1' to only view favorites",
                        "schema": {"type": "string", "enum": ["1"]}
                    },
                    {
                        "name": "page",
                        "in": "query",
                        "description": "Page number (defaults to 1)",
                        "schema": {"type": "integer", "default": 1}
                    }
                ],
                "responses": {
                    "200": {"description": "HTML page with recipes"}
                }
            }
        },
        "/recipe/{recipe_id}": {
            "get": {
                "tags": ["Recipe Web & Actions"],
                "summary": "View recipe details",
                "description": "Renders the detail view for a specific recipe.",
                "operationId": "getRecipe",
                "parameters": [
                    {
                        "name": "recipe_id",
                        "in": "path",
                        "required": True,
                        "description": "ID of the recipe",
                        "schema": {"type": "integer", "example": 1}
                    }
                ],
                "responses": {
                    "200": {"description": "HTML page with recipe detail"},
                    "404": {"description": "Recipe not found"}
                }
            }
        },
        "/add": {
            "post": {
                "tags": ["Recipe Web & Actions"],
                "summary": "Add a recipe (Form submission)",
                "description": "Submits form data to create a new recipe.",
                "operationId": "addRecipe",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "required": ["title", "instructions"],
                                "properties": {
                                    "title": {"type": "string", "example": "Guacamole"},
                                    "instructions": {"type": "string", "example": "Mash avocados with lime juice and salt..."},
                                    "servings": {"type": "integer", "default": 4, "example": 4},
                                    "tags": {"type": "string", "example": "mexican, dip, quick"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "302": {"description": "Redirects to home page on success"}
                }
            }
        },
        "/edit/{recipe_id}": {
            "post": {
                "tags": ["Recipe Web & Actions"],
                "summary": "Edit an existing recipe",
                "operationId": "editRecipe",
                "parameters": [
                    {
                        "name": "recipe_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer", "example": 1}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "required": ["title", "instructions"],
                                "properties": {
                                    "title": {"type": "string"},
                                    "instructions": {"type": "string"},
                                    "servings": {"type": "integer", "default": 4},
                                    "tags": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "302": {"description": "Redirects to recipe page on success"},
                    "404": {"description": "Recipe not found"}
                }
            }
        },
        "/favorite/{recipe_id}": {
            "post": {
                "tags": ["Recipe Web & Actions"],
                "summary": "Toggle favorite",
                "description": "Toggles whether a recipe is marked as a favorite.",
                "operationId": "toggleFavorite",
                "parameters": [
                    {
                        "name": "recipe_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer", "example": 1}
                    }
                ],
                "responses": {
                    "302": {"description": "Redirects back to referring page"}
                }
            }
        },
        "/rate/{recipe_id}": {
            "post": {
                "tags": ["Recipe Web & Actions"],
                "summary": "Rate a recipe",
                "description": "Sets a star rating (1-5) for the recipe.",
                "operationId": "rateRecipe",
                "parameters": [
                    {
                        "name": "recipe_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer", "example": 1}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "required": ["rating"],
                                "properties": {
                                    "rating": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 5,
                                        "example": 5
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "302": {"description": "Redirects to recipe page"}
                }
            }
        },
        "/delete/{recipe_id}": {
            "post": {
                "tags": ["Recipe Web & Actions"],
                "summary": "Delete a recipe (Form submission)",
                "operationId": "deleteRecipeForm",
                "parameters": [
                    {
                        "name": "recipe_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer", "example": 1}
                    }
                ],
                "responses": {
                    "302": {"description": "Redirects to home page"}
                }
            }
        }
    }
}

SWAGGER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Recipe Box - Swagger API Testing UI</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-32x32.png" sizes="32x32" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-16x16.png" sizes="16x16" />
  <style>
    html {
      box-sizing: border-box;
      overflow-y: scroll;
    }
    *, *:before, *:after {
      box-sizing: inherit;
    }
    body {
      margin: 0;
      background: #fafafa;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .swagger-ui .topbar {
      display: none;
    }
    .custom-header {
      background: #1e1e24;
      color: #fff;
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .custom-header .brand {
      font-size: 1.1rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .custom-header .badge {
      background: #49cc90;
      color: #fff;
      font-size: 0.75rem;
      padding: 3px 8px;
      border-radius: 4px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .custom-header a {
      color: #ffaa40;
      text-decoration: none;
      font-weight: 600;
      font-size: 0.95rem;
      transition: color 0.15s;
    }
    .custom-header a:hover {
      color: #ffc57a;
      text-decoration: underline;
    }
    .swagger-ui .info {
      margin: 25px 0 20px;
    }
  </style>
</head>
<body>
  <div class="custom-header">
    <div class="brand">
      <span>🍲 Recipe Box</span>
      <span class="badge">API Testing UI</span>
    </div>
    <div>
      <a href="/">← Back to Recipe Box</a>
    </div>
  </div>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js" crossorigin></script>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js" crossorigin></script>
  <script>
    window.onload = function() {
      const ui = SwaggerUIBundle({
        url: "{{ spec_url }}",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        plugins: [
          SwaggerUIBundle.plugins.DownloadUrl
        ],
        layout: "StandaloneLayout",
        defaultModelsExpandDepth: 1,
        defaultModelExpandDepth: 1,
        docExpansion: "list",
        filter: true,
        showExtensions: true,
        showCommonExtensions: true,
        tryItOutEnabled: true
      });
      window.ui = ui;
    };
  </script>
</body>
</html>
"""


@swagger_bp.route("/swagger.json")
def swagger_json():
    """Returns the OpenAPI 3.0 specification in JSON format."""
    return jsonify(SWAGGER_SPEC)


@swagger_bp.route("/swagger")
@swagger_bp.route("/docs")
@swagger_bp.route("/apidocs")
def swagger_ui():
    """Renders the interactive Swagger UI."""
    return render_template_string(SWAGGER_HTML_TEMPLATE, spec_url="/swagger.json")

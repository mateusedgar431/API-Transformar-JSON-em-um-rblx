from flask import Flask, request, jsonify
import requests
import xml.sax.saxutils as saxutils

app = Flask(__name__)

SERVICOS_MESTRES = {
    "workspace": "Workspace",
    "lighting": "Lighting",
    "replicatedfirst": "ReplicatedFirst",
    "replicatedstorage": "ReplicatedStorage",
    "serverscriptservice": "ServerScriptService",
    "serverstorage": "ServerStorage",
    "startergui": "StarterGui",
    "starterplayer": "StarterPlayer",
    "starterpack": "StarterPack",
    "teams": "Teams",
    "soundservice": "SoundService",
    "httpservice": "HttpService",
    "testservice": "TestService",
    "voicechatservice": "VoiceChatService",
    "localizationservice": "LocalizationService",
    "chat": "Chat"
}

# Lista de propriedades que o Roblox exige estritamente como <bool>
PROPRIEDADES_BOOLEANAS = {
    "IgnoreGuiInset", "Enabled", "Visible", "ResetOnSpawn", "Archivable",
    "Anchored", "CanCollide", "CanTouch", "CanQuery", "CastShadow",
    "Massless", "Locked", "ClipToDeviceSafeArea", "ClipsDescendants",
    "Active", "AutoButtonColor", "Selected", "RichText", "TextScaled",
    "TextWrapped", "ClearTextOnFocus", "MultiLine", "DisplayOrder"
}

# Tabela expandida de Tokens Enum oficiais do Roblox
MAPA_ENUM_NUMERICO = {
    # ScreenOrientation (StarterGui / ScreenGui)
    "LandscapeLeft": 0,
    "LandscapeRight": 1,
    "Portrait": 2,
    "Sensor": 3,
    "LandscapeSensor": 4,

    # Face / NormalId (Decal, Texture, SurfaceGui)
    "Right": 0,
    "Top": 1,
    "Back": 2,
    "Left": 3,
    "Bottom": 4,
    "Front": 5,

    # Fonts
    "Legacy": 0, "Arial": 1, "ArialBold": 2, "SourceSans": 3, "SourceSansBold": 4,
    "SourceSansItalic": 5, "SourceSansLight": 6, "SourceSansSemibold": 7,
    "Bodoni": 8, "Garamond": 9, "Courier": 10, "Animate": 11, "Gotham": 12,
    "GothamSemibold": 13, "GothamBold": 14, "GothamBlack": 15, "FredokaOne": 16,
    "Arcade": 17, "FiraMono": 18, "Roboto": 19, "RobotoCondensed": 20, "RobotoMono": 21,

    # ScaleType / SizeConstraint / AutomaticSize / SortOrder
    "Stretch": 0, "Tile": 1, "Slice": 2, "Fit": 3, "Crop": 4,
    "RelativeXY": 0, "RelativeXX": 1, "RelativeYY": 2, "None": 0,
    "X": 1, "Y": 2, "XY": 3,
    "LayoutOrder": 0, "Name": 1,

    # Material
    "Plastic": 256, "SmoothPlastic": 272, "Neon": 288, "Wood": 512,
    "WoodPlanks": 528, "Marble": 784, "Basalt": 788, "Slate": 800,
    "CrackedLava": 804, "Concrete": 816, "Granite": 832, "Brick": 848,
    "Pebble": 864, "Cobblestone": 880, "Rock": 896, "Sand": 1280,
    "Fabric": 1296, "Ice": 1536, "Glass": 1568, "ForceField": 1584,
    "Foil": 1792, "Metal": 1056, "DiamondPlate": 1072, "CorrodedMetal": 1088,

    # Technology / Lighting
    "Compatibility": 0, "Voxel": 1, "ShadowMap": 2, "Future": 3,

    # SurfaceType / FormFactor / PartType
    "Smooth": 0, "Glue": 1, "Weld": 2, "Studs": 3, "Inlet": 4, "Universal": 5, "Hinge": 6, "Motor": 7,
    "Ball": 0, "Block": 1, "Cylinder": 2, "Wedge": 3, "CornerWedge": 4,

    # ZIndexBehavior
    "Global": 0,
    "Sibling": 1
}

def converter_cor(valor):
    r, g, b = 0.0, 0.0, 0.0
    if isinstance(valor, dict):
        r = float(valor.get("R", valor.get("r", 0.0)))
        g = float(valor.get("G", valor.get("g", 0.0)))
        b = float(valor.get("B", valor.get("b", 0.0)))
    elif isinstance(valor, (list, tuple)) and len(valor) >= 3:
        r, g, b = float(valor[0]), float(valor[1]), float(valor[2])

    rf = r / 255.0 if r > 1.0 else r
    gf = g / 255.0 if g > 1.0 else g
    bf = b / 255.0 if b > 1.0 else b

    return rf, gf, bf

def tratar_propriedade_individual(nome_prop, valor):
    if valor is None or nome_prop in ["ClassName", "Name", "Parent", "FormFactor"]:
        return ""

    # 1. TRATAMENTO ESTRITO DE BOOLEANOS (IgnoreGuiInset, Enabled, etc)
    if isinstance(valor, bool) or nome_prop in PROPRIEDADES_BOOLEANAS:
        if isinstance(valor, str):
            val_bool_str = "true" if valor.lower() in ["true", "1", "yes"] else "false"
        else:
            val_bool_str = "true" if bool(valor) is True else "false"
        return f'<bool name="{nome_prop}">{val_bool_str}</bool>'

    # 2. STRINGS E ENUMS (ScreenOrientation, Face, Material, etc)
    if isinstance(valor, str):
        val_limpo = valor.strip()
        
        # Remove prefixo 'Enum.Grupo.Nome' se existir
        if "Enum." in val_limpo:
            val_limpo = val_limpo.split(".")[-1]

        # Mapeamento para token numérico
        if val_limpo in MAPA_ENUM_NUMERICO:
            token_val = MAPA_ENUM_NUMERICO[val_limpo]
            return f'<token name="{nome_prop}">{token_val}</token>'

        # Conteúdo de Asset/Textura
        if nome_prop in ["Texture", "Image", "TextureId", "ImageId", "MeshId", "SoundId"] or val_limpo.startswith("rbxassetid://"):
            return f'<Content name="{nome_prop}"><url>{saxutils.escape(val_limpo)}</url></Content>'

        # String padrão
        return f'<string name="{nome_prop}">{saxutils.escape(val_limpo)}</string>'

    # 3. DICIONÁRIOS / TABELAS (UDim, UDim2, Vector3, Color3, Enums em Tabela)
    if isinstance(valor, dict):
        # Enum vindo em formato de tabela Luau {EnumType = ..., Name = "Sensor"}
        if "Name" in valor:
            nome_enum = str(valor["Name"]).strip()
            if nome_enum in MAPA_ENUM_NUMERICO:
                return f'<token name="{nome_prop}">{MAPA_ENUM_NUMERICO[nome_enum]}</token>'

        # UDim2
        if "X" in valor and "Y" in valor and isinstance(valor.get("X"), dict) and isinstance(valor.get("Y"), dict):
            xs = float(valor["X"].get("Scale", valor["X"].get("scale", 0)))
            xo = int(valor["X"].get("Offset", valor["X"].get("offset", 0)))
            ys = float(valor["Y"].get("Scale", valor["Y"].get("scale", 0)))
            yo = int(valor["Y"].get("Offset", valor["Y"].get("offset", 0)))
            return f'<UDim2 name="{nome_prop}"><XS>{xs}</XS><XO>{xo}</XO><YS>{ys}</YS><YO>{yo}</YO></UDim2>'

        # UDim (Simples)
        if ("Scale" in valor or "scale" in valor) and ("Offset" in valor or "offset" in valor) and "X" not in valor:
            s = float(valor.get("Scale", valor.get("scale", 0)))
            o = int(valor.get("Offset", valor.get("offset", 0)))
            return f'<UDim name="{nome_prop}"><S>{s}</S><O>{o}</O></UDim>'

        # Vector3
        if "X" in valor and "Y" in valor and "Z" in valor:
            return f'<Vector3 name="{nome_prop}"><X>{float(valor["X"])}</X><Y>{float(valor["Y"])}</Y><Z>{float(valor["Z"])}</Z></Vector3>'

        # Vector2
        if "X" in valor and "Y" in valor and "Z" not in valor:
            return f'<Vector2 name="{nome_prop}"><X>{float(valor["X"])}</X><Y>{float(valor["Y"])}</Y></Vector2>'

        # Color3
        if ("R" in valor or "r" in valor) and ("G" in valor or "g" in valor) and ("B" in valor or "b" in valor):
            rf, gf, bf = converter_cor(valor)
            return f'<Color3 name="{nome_prop}"><R>{rf}</R><G>{gf}</G><B>{bf}</B></Color3>'

    # 4. ARRAYS (CFrame)
    if isinstance(valor, list):
        if len(valor) in [12, 16]:
            return f'''<CoordinateFrame name="{nome_prop}">
                <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
                <R00>{valor[3]}</R00><R01>{valor[4]}</R01><R02>{valor[5]}</R02>
                <R10>{valor[6]}</R10><R11>{valor[7]}</R11><R12>{valor[8]}</R12>
                <R20>{valor[9]}</R20><R21>{valor[10]}</R21><R22>{valor[11]}</R22>
            </CoordinateFrame>'''

    # 5. NÚMEROS / TOKENS
    if isinstance(valor, float):
        return f'<float name="{nome_prop}">{valor}</float>'

    if isinstance(valor, int):
        # Se for propriedade conhecida de Enum e vier como número direto, envia como token
        if nome_prop in ["ScreenOrientation", "Face", "Material", "Font", "ScaleType", "SortOrder"]:
            return f'<token name="{nome_prop}">{valor}</token>'
        return f'<int name="{nome_prop}">{valor}</int>'

    return ""

def processar_dicionario_propriedades(props_dict):
    xml_props = []
    for k, v in props_dict.items():
        no_xml = tratar_propriedade_individual(k, v)
        if no_xml:
            xml_props.append(f"            {no_xml}")
    return "\n".join(xml_props)

def processar_objetos_xml(TableData):
    xml_output = []
    if isinstance(TableData, list):
        for idx, a in enumerate(TableData):
            if isinstance(a, dict):
                props = a.get("Properties", {})
                children = a.get("Children", []) or a.get("Objects", [])
                script_code = a.get("Script") or (props.get("Source") if isinstance(props, dict) else None)

                if not isinstance(props, dict):
                    props = {}

                class_name = props.get("ClassName", "Part")
                obj_name = props.get("Name", f"Object_{idx}")

                ref_id = f"RBX_OBJ_{idx}_{abs(hash(obj_name))}"

                item_str = f'<Item class="{class_name}" referent="{ref_id}">\n  <Properties>\n    <string name="Name">{saxutils.escape(str(obj_name))}</string>'
                props_xml = processar_dicionario_propriedades(props)
                if props_xml:
                    item_str += f"\n{props_xml}"

                if script_code or class_name in ["Script", "LocalScript", "ModuleScript"]:
                    codigo_str = str(script_code) if script_code is not None else ""
                    item_str += f'\n    <ProtectedString name="Source">{saxutils.escape(codigo_str)}</ProtectedString>'

                item_str += '\n  </Properties>'

                if children and isinstance(children, list):
                    item_str += processar_objetos_xml(children)

                item_str += '\n</Item>'
                xml_output.append(item_str)

    return "\n".join(xml_output)

def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    workspace_props = ""
    servicos_dados_finais = {
        s_nome: {"props": {}, "objects": []} 
        for s_nome in SERVICOS_MESTRES.values() if s_nome != "Workspace"
    }

    if isinstance(part_data_dict, dict):
        for chave_entrada, servico_dados in part_data_dict.items():
            chave_low = str(chave_entrada).strip().lower()
            servico_oficial = SERVICOS_MESTRES.get(chave_low)

            if not servico_oficial:
                continue

            objetos = []
            propriedades_recebidas = {}

            if isinstance(servico_dados, dict):
                objetos = servico_dados.get("Objects", []) or servico_dados.get("Children", [])
                if "Properties" in servico_dados and isinstance(servico_dados["Properties"], dict):
                    propriedades_recebidas = servico_dados["Properties"]
                else:
                    propriedades_recebidas = {k: v for k, v in servico_dados.items() if k not in ["Objects", "Children"]}

            elif isinstance(servico_dados, list):
                objetos = servico_dados

            if servico_oficial == "Workspace":
                workspace_content = processar_objetos_xml(objetos)
                workspace_props = processar_dicionario_propriedades(propriedades_recebidas)
            else:
                servicos_dados_finais[servico_oficial]["props"].update(propriedades_recebidas)
                servicos_dados_finais[servico_oficial]["objects"] = objetos

    elif isinstance(part_data_dict, list):
        workspace_content = processar_objetos_xml(part_data_dict)

    outros_servicos_list = []
    for s_nome, dados in servicos_dados_finais.items():
        ref_servico = f"RBX_SERVICE_{s_nome.upper()}"
        props_xml = processar_dicionario_propriedades(dados["props"])
        objs_xml = processar_objetos_xml(dados["objects"])

        outros_servicos_list.append(f'''
    <Item class="{s_nome}" referent="{ref_servico}">
        <Properties>
            <string name="Name">{s_nome}</string>
{props_xml}
        </Properties>
{objs_xml}
    </Item>''')

    outros_servicos_str = "".join(outros_servicos_list)

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE_ROOT">
        <Properties>
            <string name="Name">Workspace</string>
            <bool name="FilteringEnabled">true</bool>
{workspace_props}
        </Properties>
        {workspace_content}
    </Item>{outros_servicos_str}
</roblox>'''

    return rbxlx_str.encode('utf-8')

@app.route('/publicar', methods=['POST'])
def publicar():
    try:
        dados_json = request.json
        api_key = request.headers.get('x-api-key')
        universe_id = request.headers.get('universe-id')
        place_id = request.headers.get('place-id')

        if not api_key or not universe_id or not place_id:
            return jsonify({"erro": "Headers obrigatorios faltando."}), 400

        conteudo_rbxlx = construir_rbxlx_completo(dados_json)

        url_roblox = f"https://apis.roblox.com/universes/v1/{universe_id}/places/{place_id}/versions?versionType=Published"
        headers_roblox = {
            "x-api-key": api_key,
            "Content-Type": "application/xml",
            "User-Agent": "RobloxOpenCloudClient/1.0"
        }

        resposta = requests.post(url_roblox, headers=headers_roblox, data=conteudo_rbxlx)

        return jsonify({
            "status": resposta.status_code,
            "resposta_roblox": resposta.text
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/carregarasset", methods=['GET'])
def carregarasset():
  try:
    asset_id = None

    # Captura o assetId via GET (Query String) ou POST (JSON / Form Data)
    if request.method == "GET":
      asset_id = request.args.get('assetId') or request.args.get('id')
    elif request.method == "POST":
      if request.is_json:
        data = request.get_json() or {}
        asset_id = data.get('assetId') or data.get('id')
      else:
        asset_id = request.form.get('assetId') or request.form.get('id')

    if not asset_id:
      return jsonify({"status": 400, "erro": "Asset ID nao informado"})

    # Requisição para a API v2 do Roblox com todas as headers obrigatórias
    roblox_url = f"https://assetdelivery.roblox.com/v2/assetId/{asset_id}"
    headers = {
        "User-Agent": "Roblox/WinInet",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Roblox-Place-Id": "0",
        "AssetType": "Model",
        "AssetFormat": "Binary",
        "Roblox-AssetFormat": "Binary",
    }

    res = requests.get(
        roblox_url, headers=headers, timeout=15, allow_redirects=True
    )

    if res.status_code != 200:
      return (
          jsonify(
              {"status": f"Status do Roblox: {res.status_code}", "resposta": res.text}
          ),
      )

    # Retorna o binário (.rbxm) baixado diretamente para o Roblox Studio ou Navegador
    return flask.Response(
        res.content, status=200, content_type="application/octet-stream"
    )

  except Exception as err:
    return jsonify({"status": 500, "resposta": str(err)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

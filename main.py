from flask import Flask, request, jsonify
import requests
import xml.sax.saxutils as saxutils

app = Flask(__name__)

SERVICOS_OFICIAIS = {
    "Workspace": "Workspace",
    "Lighting": "Lighting",
    "ReplicatedFirst": "ReplicatedFirst",
    "ReplicatedStorage": "ReplicatedStorage",
    "ServerScriptService": "ServerScriptService",
    "ServerStorage": "ServerStorage",
    "StarterGui": "StarterGui",
    "StarterPlayer": "StarterPlayer",
    "StarterPack": "StarterPack",
    "Teams": "Teams",
    "SoundService": "SoundService",
    "MaterialService": "MaterialService"
}

MAPA_ENUM_TEXTO_PARA_ID = {
    "Right": 0, "Top": 1, "Back": 2, "Left": 3, "Bottom": 4, "Front": 5,
    "Smooth": 0, "Glue": 1, "Weld": 2, "Studs": 3, "Inlet": 4, 
    "Universal": 5, "Hinge": 6, "Motor": 7, "SteppingMotor": 8,
    "Ball": 0, "Block": 1, "Cylinder": 2, "Wedge": 3,
    "Linear": 0, "In": 0, "Out": 1, "InOut": 2, "Sine": 1, "Quad": 3
}

def normalizar_valor_token(nome_prop, valor):
    if isinstance(valor, dict):
        if "Name" in valor and valor["Name"]:
            valor = valor["Name"]
        elif "Value" in valor:
            valor = valor["Value"]

    if isinstance(valor, str):
        nome_limpo = valor.split(".")[-1]
        if nome_prop == "Material":
            return nome_limpo
        if nome_limpo in MAPA_ENUM_TEXTO_PARA_ID:
            return str(MAPA_ENUM_TEXTO_PARA_ID[nome_limpo])
        if nome_limpo.isdigit():
            return nome_limpo
        return nome_limpo

    if isinstance(valor, int):
        return str(valor)

    return str(valor)

def processar_propriedade_xml(nome_prop, valor, props_dict):
    if valor is None or nome_prop in ["ClassName", "Name", "Parent", "FormFactor"]:
        return ""

    if isinstance(props_dict, dict) and "CFrame" in props_dict and nome_prop in ["Position", "Orientation", "Rotation"]:
        return ""

    # 1. CFRAME
    if nome_prop == "CFrame" and isinstance(valor, list) and len(valor) >= 12:
        return f'''
            <CoordinateFrame name="CFrame">
                <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
                <R00>{valor[3]}</R00><R01>{valor[4]}</R01><R02>{valor[5]}</R02>
                <R10>{valor[6]}</R10><R11>{valor[7]}</R11><R12>{valor[8]}</R12>
                <R20>{valor[9]}</R20><R21>{valor[10]}</R21><R22>{valor[11]}</R22>
            </CoordinateFrame>'''

    # 2. BOOLEANOS
    if isinstance(valor, bool):
        val_str = "true" if valor else "false"
        return f'\n            <bool name="{nome_prop}">{val_str}</bool>'

    # 3. ENUMS / TOKENS
    e_enum = (
        nome_prop in ["Shape", "Font", "PartType", "Face", "NormalId", "Technology", "CameraType"] or
        nome_prop.endswith("Surface") or
        nome_prop.endswith("Type") or 
        nome_prop.endswith("Style") or 
        nome_prop.endswith("Mode") or 
        nome_prop.endswith("Alignment") or 
        nome_prop.endswith("Direction")
    )

    if e_enum or (isinstance(valor, str) and "Enum." in valor):
        val_token = normalizar_valor_token(nome_prop, valor)
        return f'\n            <token name="{nome_prop}">{val_token}</token>'

    # 4. TRATAMENTO ESPECÍFICO PARA LIGHTING E PROPRIEDADES NATIVAS DE SERVIÇOS
    if nome_prop == "ClockTime":
        return f'\n            <float name="ClockTime">{float(valor)}</float>'
    if nome_prop == "TimeOfDay":
        return f'\n            <string name="TimeOfDay">{saxutils.escape(str(valor))}</string>'
    if nome_prop in ["GeographicLatitude", "Brightness", "ExposureCompensation", "ShadowSoftness"]:
        return f'\n            <float name="{nome_prop}">{float(valor)}</float>'

    # 5. FLOATS GERAIS
    if isinstance(valor, float):
        return f'\n            <float name="{nome_prop}">{float(valor)}</float>'

    # 6. INTEIROS
    if isinstance(valor, int):
        return f'\n            <int name="{nome_prop}">{valor}</int>'

    # 7. DICIONÁRIOS (Color3 / Color3uint8 / Vector3 / UDim2)
    if isinstance(valor, dict):
        if "X" in valor and "Y" in valor and isinstance(valor.get("X"), dict):
            x_dict, y_dict = valor.get("X", {}), valor.get("Y", {})
            return f'''
            <UDim2 name="{nome_prop}">
                <XS>{x_dict.get("Scale", 0)}</XS>
                <XO>{x_dict.get("Offset", 0)}</XO>
                <YS>{y_dict.get("Scale", 0)}</YS>
                <YO>{y_dict.get("Offset", 0)}</YO>
            </UDim2>'''

        if "X" in valor and "Y" in valor and "Z" in valor:
            return f'''
            <Vector3 name="{nome_prop}">
                <X>{valor.get("X", 0)}</X><Y>{valor.get("Y", 0)}</Y><Z>{valor.get("Z", 0)}</Z>
            </Vector3>'''

        if "R" in valor and "G" in valor and "B" in valor:
            r = valor["R"]
            g = valor["G"]
            b = valor["B"]
            
            # Converte valores 0-255 para ponto flutuante 0.0 - 1.0 exigido no XML nativo
            rf = r / 255.0 if r > 1.0 else float(r)
            gf = g / 255.0 if g > 1.0 else float(g)
            bf = b / 255.0 if b > 1.0 else float(b)

            return f'''
            <Color3 name="{nome_prop}">
                <R>{rf}</R>
                <G>{gf}</G>
                <B>{bf}</B>
            </Color3>'''

    # 8. STRINGS
    if isinstance(valor, str):
        if nome_prop in ["Texture", "Image", "TextureId", "ImageId", "MeshId", "SoundId"] or valor.startswith("rbxassetid://"):
            return f'\n            <Content name="{nome_prop}"><url>{saxutils.escape(valor)}</url></Content>'

        return f'\n            <string name="{nome_prop}">{saxutils.escape(str(valor))}</string>'

    return ""

def processar_objetos_xml(TableData):
    xml_output = ""

    if isinstance(TableData, list):
        for idx, a in enumerate(TableData):
            if isinstance(a, dict):
                props = a.get("Properties", {})
                children = a.get("Children", [])
                script_code = a.get("Script")

                if not isinstance(props, dict):
                    props = {}

                class_name = props.get("ClassName", "Part")
                obj_name = props.get("Name", f"Object_{idx}")

                if script_code and class_name not in ["Script", "LocalScript", "ModuleScript"]:
                    class_name = "Script"

                ref_id = f"RBX_OBJ_{idx}_{abs(hash(obj_name))}"

                xml_output += f'\n<Item class="{class_name}" referent="{ref_id}">'
                xml_output += '\n  <Properties>'
                xml_output += f'\n    <string name="Name">{saxutils.escape(str(obj_name))}</string>'

                if class_name in ["Part", "WedgePart", "CornerWedgePart", "MeshPart", "SpawnLocation", "BasePart"]:
                    if "Anchored" not in props:
                        props["Anchored"] = True
                    if "CanCollide" not in props:
                        props["CanCollide"] = True

                for nome_prop, val_prop in props.items():
                    xml_output += processar_propriedade_xml(nome_prop, val_prop, props)

                if script_code or class_name in ["Script", "LocalScript", "ModuleScript"]:
                    codigo_str = str(script_code) if script_code is not None else ""
                    codigo_escapado = saxutils.escape(codigo_str)
                    xml_output += f'\n            <ProtectedString name="Source">{codigo_escapado}</ProtectedString>'

                xml_output += '\n  </Properties>'

                if children and isinstance(children, list):
                    xml_output += processar_objetos_xml(children)

                xml_output += '\n</Item>'

    return xml_output

def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    servicos_xml = {}

    # Inicializa os serviços
    for s_nome in SERVICOS_OFICIAIS.keys():
        if s_nome != "Workspace":
            servicos_xml[s_nome] = {"props": "", "objects": ""}

    if isinstance(part_data_dict, dict):
        for servico_nome, servico_dados in part_data_dict.items():
            objetos = []
            propriedades_servico = {}

            if isinstance(servico_dados, dict):
                objetos = servico_dados.get("Objects", [])
                propriedades_servico = servico_dados.get("Properties", {})
            elif isinstance(servico_dados, list):
                objetos = servico_dados

            if servico_nome == "Workspace":
                workspace_content += processar_objetos_xml(objetos)
            else:
                str_props = f'\n    <string name="Name">{servico_nome}</string>'
                for k, v in propriedades_servico.items():
                    str_props += processar_propriedade_xml(k, v, propriedades_servico)

                str_objs = processar_objetos_xml(objetos)

                servicos_xml[servico_nome] = {
                    "props": str_props,
                    "objects": str_objs
                }

    elif isinstance(part_data_dict, list):
        workspace_content = processar_objetos_xml(part_data_dict)

    outros_servicos_str = ""
    for s_nome, s_classe in SERVICOS_OFICIAIS.items():
        if s_nome == "Workspace":
            continue

        dados = servicos_xml.get(s_nome, {"props": f'\n    <string name="Name">{s_nome}</string>', "objects": ""})
        ref_servico = f"RBX_SERVICE_{s_nome.upper()}"

        outros_servicos_str += f'''
    <Item class="{s_classe}" referent="{ref_servico}">
        <Properties>{dados["props"]}
        </Properties>{dados["objects"]}
    </Item>'''

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE_ROOT">
        <Properties>
            <string name="Name">Workspace</string>
            <bool name="FilteringEnabled">true</bool>
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

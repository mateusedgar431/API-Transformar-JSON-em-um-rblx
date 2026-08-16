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

def processar_propriedade_xml(nome_prop, valor, props_dict):
    if valor is None or nome_prop in ["ClassName", "Name", "Parent"]:
        return ""

    # Se tiver CFrame, ignora Position e Orientation duplicados para não dar conflito
    if "CFrame" in props_dict and nome_prop in ["Position", "Orientation", "Rotation"]:
        return ""

    # 1. CFRAME
    if nome_prop == "CFrame":
        if isinstance(valor, list) and len(valor) >= 12:
            return f'''
            <CoordinateFrame name="CFrame">
                <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
                <R00>{valor[3]}</R00><R01>{valor[4]}</R01><R02>{valor[5]}</R02>
                <R10>{valor[6]}</R10><R11>{valor[7]}</R11><R12>{valor[8]}</R12>
                <R20>{valor[9]}</R20><R21>{valor[10]}</R21><R22>{valor[11]}</R22>
            </CoordinateFrame>'''

    # 2. UDIM2 (Fundamental para StarterGui / ScreenGui / TextLabel / Frame)
    elif isinstance(valor, dict) and ("X" in valor and "Y" in valor) and (isinstance(valor["X"], dict) or "Scale" in valor.get("X", {})):
        x_s = valor["X"].get("Scale", 0)
        x_o = valor["X"].get("Offset", 0)
        y_s = valor["Y"].get("Scale", 0)
        y_o = valor["Y"].get("Offset", 0)
        return f'''
            <UDim2 name="{nome_prop}">
                <XS>{x_s}</XS>
                <XO>{x_o}</XO>
                <YS>{y_s}</YS>
                <YO>{y_o}</YO>
            </UDim2>'''

    # 3. VETORES (Vector3 / Vector2)
    elif isinstance(valor, dict) and "X" in valor and "Y" in valor and "Z" in valor:
        return f'''
            <Vector3 name="{nome_prop}">
                <X>{valor["X"]}</X><Y>{valor["Y"]}</Y><Z>{valor["Z"]}</Z>
            </Vector3>'''
    elif isinstance(valor, dict) and "X" in valor and "Y" in valor:
        return f'''
            <Vector2 name="{nome_prop}">
                <X>{valor["X"]}</X><Y>{valor["Y"]}</Y>
            </Vector2>'''
    elif isinstance(valor, list) and len(valor) == 3:
        return f'''
            <Vector3 name="{nome_prop}">
                <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
            </Vector3>'''

    # 4. CORES (Color3uint8 / Color3)
    elif isinstance(valor, dict) and "R" in valor and "G" in valor and "B" in valor:
        r = int(valor["R"] * 255) if isinstance(valor["R"], float) and valor["R"] <= 1.0 else int(valor["R"])
        g = int(valor["G"] * 255) if isinstance(valor["G"], float) and valor["G"] <= 1.0 else int(valor["G"])
        b = int(valor["B"] * 255) if isinstance(valor["B"], float) and valor["B"] <= 1.0 else int(valor["B"])
        cor_uint = (r << 16) | (g << 8) | b
        return f'\n            <Color3uint8 name="{nome_prop}">{cor_uint}</Color3uint8>'

    # 5. BOOLEANOS
    elif isinstance(valor, bool):
        val_str = "true" if valor else "false"
        return f'\n            <bool name="{nome_prop}">{val_str}</bool>'

    # 6. NÚMEROS (Floats vs Ints tratados por propriedade conhecida)
    elif isinstance(valor, (int, float)):
        props_int = ["ZIndex", "LayoutOrder", "BorderSizePixel", "TextSize"]
        if nome_prop in props_int or isinstance(valor, int):
            return f'\n            <int name="{nome_prop}">{int(valor)}</int>'
        return f'\n            <float name="{nome_prop}">{float(valor)}</float>'

    # 7. ENUMS, STRINGS E ASSETS
    elif isinstance(valor, str):
        if "Enum." in valor:
            enum_val = valor.split(".")[-1]
            return f'\n            <token name="{nome_prop}">{enum_val}</token>'
        if nome_prop in ["Texture", "Image", "TextureId", "ImageId", "MeshId", "SoundId"] or valor.startswith("rbxassetid://"):
            return f'\n            <Content name="{nome_prop}"><url>{saxutils.escape(valor)}</url></Content>'
        return f'\n            <string name="{nome_prop}">{saxutils.escape(valor)}</string>'

    return ""


def processar_objetos_xml(TableData):
    xml_output = ""

    if isinstance(TableData, list):
        for idx, a in enumerate(TableData):
            if isinstance(a, dict):
                props = a.get("Properties", {})
                children = a.get("Children", [])
                script_code = a.get("Script")

                class_name = props.get("ClassName", "Part")
                obj_name = props.get("Name", f"Object_{idx}")

                if script_code and class_name not in ["Script", "LocalScript", "ModuleScript"]:
                    class_name = "Script"

                ref_id = f"RBX_OBJ_{idx}_{abs(hash(obj_name))}"

                xml_output += f'\n<Item class="{class_name}" referent="{ref_id}">'
                xml_output += '\n  <Properties>'
                xml_output += f'\n    <string name="Name">{saxutils.escape(obj_name)}</string>'

                # Propriedades padrão vitais para a GUI aparecer na tela
                if class_name == "ScreenGui":
                    if "ResetOnSpawn" not in props:
                        props["ResetOnSpawn"] = True
                    if "Enabled" not in props:
                        props["Enabled"] = True

                if class_name in ["Part", "WedgePart", "CornerWedgePart", "MeshPart", "SpawnLocation", "BasePart"]:
                    if "Anchored" not in props:
                        props["Anchored"] = True
                    if "CanCollide" not in props:
                        props["CanCollide"] = True

                # Processa todas as propriedades
                if isinstance(props, dict):
                    for nome_prop, val_prop in props.items():
                        xml_output += processar_propriedade_xml(nome_prop, val_prop, props)

                # Código-fonte para Scripts
                if script_code or class_name in ["Script", "LocalScript", "ModuleScript"]:
                    codigo_str = str(script_code) if script_code is not None else ""
                    codigo_escapado = saxutils.escape(codigo_str)
                    xml_output += f'\n            <ProtectedString name="Source">{codigo_escapado}</ProtectedString>'

                xml_output += '\n  </Properties>'

                # Processa os filhos (Essencial para GUIs dentro de ScreenGui e peças dentro de Folders)
                if children and isinstance(children, list):
                    xml_output += processar_objetos_xml(children)

                xml_output += '\n</Item>'

    return xml_output


def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    outros_servicos = ""

    if isinstance(part_data_dict, dict):
        for servico_nome, servico_dados in part_data_dict.items():
            objetos = servico_dados.get("Objects", []) if isinstance(servico_dados, dict) else servico_dados

            if servico_nome == "Workspace":
                workspace_content += processar_objetos_xml(objetos)
            else:
                classe_servico = SERVICOS_OFICIAIS.get(servico_nome, "Folder")
                ref_servico = f"RBX_SERVICE_{servico_nome.upper()}"

                outros_servicos += f'\n<Item class="{classe_servico}" referent="{ref_servico}">'
                outros_servicos += f'\n  <Properties><string name="Name">{servico_nome}</string></Properties>'
                outros_servicos += processar_objetos_xml(objetos)
                outros_servicos += '\n</Item>'

    elif isinstance(part_data_dict, list):
        workspace_content = processar_objetos_xml(part_data_dict)

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE_ROOT">
        <Properties>
            <string name="Name">Workspace</string>
            <bool name="FilteringEnabled">true</bool>
        </Properties>
        {workspace_content}
    </Item>
    {outros_servicos}
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
